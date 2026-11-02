package com.daybill.mobile

// ============================================================
// DayBill Mobile for Android — the DayBill Mobile web app inside a
// full-screen app, plus what a browser can't do:
//   • PDT scanner buttons (Zebra DataWedge, Urovo, Honeywell, Newland,
//     iData, Sunmi, Chainway …) send the barcode straight into the app
//   • camera barcode scanning (Google code scanner)
//   • Bluetooth receipt printer (58 / 80 mm ESC/POS) for van bills
//   • the server address (shop Wi-Fi or the van relay) is set once
// The web app calls window.DayBillAndroid.* (see app.js).
// ============================================================

import android.Manifest
import android.annotation.SuppressLint
import android.app.AlertDialog
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Base64
import android.view.KeyEvent
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import org.json.JSONObject
import java.util.UUID

class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private val prefs by lazy { getSharedPreferences("daybill", Context.MODE_PRIVATE) }
    private val SPP: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")

    // Scanner broadcasts of the common Android PDT brands: action → data extra(s)
    private val scanActions = mapOf(
        "com.daybill.SCAN" to listOf("com.symbol.datawedge.data_string", "data", "barcode"),     // Zebra DataWedge
        "android.intent.ACTION_DECODE_DATA" to listOf("barcode_string", "barcode"),               // Urovo
        "com.honeywell.decode.intent.action.EDIT_DATA" to listOf("data"),                         // Honeywell
        "nlscan.action.SCANNER_RESULT" to listOf("SCAN_BARCODE1"),                                // Newland
        "android.intent.action.SCANRESULT" to listOf("value"),                                    // iData
        "com.sunmi.scanner.ACTION_DATA_CODE_RECEIVED" to listOf("data"),                          // Sunmi
        "com.scanner.broadcast" to listOf("data"),                                                // Chainway / others
        "scan.rcv.message" to listOf("barocode", "barcode")                                       // older Chinese PDTs
    )

    private val scanReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context?, intent: Intent?) {
            val code = readScan(intent) ?: return
            sendScan(code)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this)
        setContentView(web)
        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            mediaPlaybackRequiresUserGesture = false
            allowFileAccess = false
            userAgentString = "$userAgentString DayBillAndroid/5.23"
        }
        web.addJavascriptInterface(Bridge(), "DayBillAndroid")
        web.webChromeClient = WebChromeClient()
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, req: WebResourceRequest): Boolean {
                val u = req.url.toString()
                if (u.startsWith("https://wa.me") || u.startsWith("intent:") || u.startsWith("tel:")) {
                    try { startActivity(Intent.parseUri(u, Intent.URI_INTENT_SCHEME)) } catch (e: Exception) {
                        Toast.makeText(this@MainActivity, "No app for this link", Toast.LENGTH_SHORT).show()
                    }
                    return true
                }
                return false
            }
            override fun onReceivedError(view: WebView, req: WebResourceRequest, err: WebResourceError) {
                if (req.isForMainFrame) showSetup("Can't open ${req.url} — ${err.description}")
            }
        }
        val filter = IntentFilter().apply { scanActions.keys.forEach { addAction(it) } }
        ContextCompat.registerReceiver(this, scanReceiver, filter, ContextCompat.RECEIVER_EXPORTED)
        val url = prefs.getString("url", "") ?: ""
        if (url.isBlank()) showSetup("") else web.loadUrl(url)
        handleIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent?) {
        readScan(intent)?.let { sendScan(it) }
    }

    private fun readScan(intent: Intent?): String? {
        if (intent == null || intent.action !in scanActions.keys) return null
        for (k in scanActions[intent.action] ?: emptyList()) {
            val v = intent.getStringExtra(k)
            if (!v.isNullOrBlank()) return v.trim()
            val b = intent.getByteArrayExtra(k)
            if (b != null && b.isNotEmpty()) return String(b).trim()
        }
        return null
    }

    private fun sendScan(code: String) {
        runOnUiThread {
            web.evaluateJavascript("window.daybillScan && window.daybillScan(${JSONObject.quote(code)})", null)
        }
    }

    private fun showSetup(problem: String) {
        val html = assets.open("setup.html").bufferedReader().use { it.readText() }
            .replace("{{URL}}", prefs.getString("url", "") ?: "")
            .replace("{{PROBLEM}}", problem.replace("<", "&lt;"))
        web.loadDataWithBaseURL("https://setup.daybill/", html, "text/html", "utf-8", null)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else {
            web.evaluateJavascript("(window.DayBillApp && window.DayBillApp.home) ? (window.DayBillApp.home(), 'home') : 'none'") {
                if (it == "\"none\"") super.onBackPressed()
            }
        }
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean = super.dispatchKeyEvent(event)

    override fun onDestroy() {
        try { unregisterReceiver(scanReceiver) } catch (_: Exception) {}
        super.onDestroy()
    }

    // ── Bluetooth printer ────────────────────────────────────
    private fun hasBtPermission(): Boolean =
        Build.VERSION.SDK_INT < 31 ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED

    private fun askBtPermission() {
        if (Build.VERSION.SDK_INT >= 31)
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.BLUETOOTH_CONNECT), 7)
    }

    @SuppressLint("MissingPermission")
    private fun choosePrinter(after: (() -> Unit)? = null) {
        if (!hasBtPermission()) { askBtPermission(); return }
        val adapter = (getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
        if (adapter == null || !adapter.isEnabled) {
            Toast.makeText(this, "Turn Bluetooth on, pair the printer in Android settings", Toast.LENGTH_LONG).show(); return
        }
        val devs = adapter.bondedDevices.toList()
        if (devs.isEmpty()) {
            Toast.makeText(this, "Pair the printer first: Android Settings ▸ Bluetooth", Toast.LENGTH_LONG).show(); return
        }
        AlertDialog.Builder(this).setTitle("Receipt printer")
            .setItems(devs.map { "${it.name ?: "?"}\n${it.address}" }.toTypedArray()) { _, i ->
                prefs.edit().putString("printer", devs[i].address).putString("printer_name", devs[i].name).apply()
                Toast.makeText(this, "Printer: ${devs[i].name}", Toast.LENGTH_SHORT).show()
                after?.invoke()
            }.show()
    }

    @SuppressLint("MissingPermission")
    private fun printBytes(data: ByteArray): String {
        if (!hasBtPermission()) { runOnUiThread { askBtPermission() }; return "Allow Bluetooth, then press Print again" }
        val mac = prefs.getString("printer", "") ?: ""
        if (mac.isBlank()) { runOnUiThread { choosePrinter() }; return "Choose the printer, then press Print again" }
        val adapter = (getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
            ?: return "No Bluetooth on this device"
        var sock: BluetoothSocket? = null
        return try {
            adapter.cancelDiscovery()
            sock = adapter.getRemoteDevice(mac).createRfcommSocketToServiceRecord(SPP)
            sock.connect()
            val out = sock.outputStream
            var i = 0
            while (i < data.size) {             // small chunks: cheap printers have tiny buffers
                val n = minOf(512, data.size - i)
                out.write(data, i, n); out.flush(); i += n
                Thread.sleep(20)
            }
            Thread.sleep(400)
            "ok"
        } catch (e: Exception) {
            "Printer: ${e.message ?: "not reachable"} — is it on and paired?"
        } finally {
            try { sock?.close() } catch (_: Exception) {}
        }
    }

    // ── what the web app can call ────────────────────────────
    inner class Bridge {
        @JavascriptInterface fun version(): String = "5.23.0"

        @JavascriptInterface fun deviceName(): String = "${Build.MANUFACTURER} ${Build.MODEL}"

        @JavascriptInterface fun scanCamera() {
            runOnUiThread {
                GmsBarcodeScanning.getClient(this@MainActivity).startScan()
                    .addOnSuccessListener { b -> b.rawValue?.let { sendScan(it) } }
                    .addOnFailureListener { e ->
                        Toast.makeText(this@MainActivity, "Camera scan: ${e.message}", Toast.LENGTH_LONG).show()
                    }
            }
        }

        @JavascriptInterface fun printEscPos(b64: String): String = printBytes(Base64.decode(b64, Base64.DEFAULT))

        @JavascriptInterface fun printerName(): String = prefs.getString("printer_name", "") ?: ""

        @JavascriptInterface fun choosePrinter() { runOnUiThread { this@MainActivity.choosePrinter() } }

        @JavascriptInterface fun serverUrl(): String = prefs.getString("url", "") ?: ""

        @JavascriptInterface fun setServer(url: String) {
            var u = url.trim()
            if (u.isBlank()) return
            // shop PC on Wi-Fi (192.168.x.x:8090) → http; the van relay (a web address) → https
            if (!u.startsWith("http")) u = (if (Regex("^[0-9.]+(:[0-9]+)?(/.*)?$").matches(u) || u.contains(":")) "http://" else "https://") + u
            val path = u.substringAfter("://").substringAfter("/", "")
            if (path.isNotEmpty() && !path.endsWith("/") && !path.substringAfterLast("/").contains(".")) u += "/"
            prefs.edit().putString("url", u).apply()
            runOnUiThread { web.clearHistory(); web.loadUrl(u) }
        }

        @JavascriptInterface fun openSettings() { runOnUiThread { showSetup("") } }
    }
}
