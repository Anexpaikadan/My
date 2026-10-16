plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.daybill.mobile"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.daybill.mobile"
        minSdk = 24
        targetSdk = 34
        versionCode = 5230
        versionName = "5.23.0"
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            // signingConfig: see README_ANDROID.md (your own keystore)
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.webkit:webkit:1.11.0")
    // camera barcode scanning (Google Play services code scanner — no camera permission needed)
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")
}
