<?php
// ================================================================
// theme.php — dark / light look for the public pages (index.php, contact.php)
//   theme_head()   : put in <head> BEFORE the stylesheets. Sets <html data-theme>
//                    before the page draws, so the wrong theme never flashes.
//   theme_button() : the sun/moon switch for the top bar.
// Default comes from Admin → Public Website → Sections → "Default look"
// (club_settings pub_theme = dark | light | auto). A visitor's choice is
// remembered on their phone (localStorage "pubTheme").
// ================================================================
require_once __DIR__ . '/og.php';
require_once __DIR__ . '/lang.php';
if (!function_exists('theme_head')) {

function theme_default() {
    $d = site_cfg('pub_theme', 'dark');
    return in_array($d, array('dark', 'light', 'auto'), true) ? $d : 'dark';
}

function theme_head() {
    $d = json_encode(theme_default());
    return '<meta name="theme-color" id="metaTheme" content="#0B1033">' . "\n"
         . '<script>(function(){var d=' . $d . ',t=null;try{t=localStorage.getItem("pubTheme")}catch(e){}'
         . 'if(t!=="light"&&t!=="dark"){t=d==="auto"?((window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches)?"light":"dark"):d;}'
         . 'document.documentElement.setAttribute("data-theme",t);'
         . 'var m=document.getElementById("metaTheme");if(m)m.setAttribute("content",t==="light"?"#F4F6FB":"#0B1033");})();</script>' . "\n";
}

function theme_button() {
    $toLight = htmlspecialchars(t('theme_light'), ENT_QUOTES, 'UTF-8');
    $toDark  = htmlspecialchars(t('theme_dark'), ENT_QUOTES, 'UTF-8');
    return '<button type="button" class="theme-tg" id="themeTg" data-to-light="' . $toLight . '" data-to-dark="' . $toDark . '" aria-label="' . $toLight . '">'
         . '<i class="bi bi-sun-fill" aria-hidden="true"></i></button>'
         . '<script>(function(){var b=document.getElementById("themeTg"),h=document.documentElement;if(!b)return;'
         . 'function sync(){var l=h.getAttribute("data-theme")==="light";b.setAttribute("aria-label",l?b.getAttribute("data-to-dark"):b.getAttribute("data-to-light"));'
         . 'b.firstChild.className="bi "+(l?"bi-moon-stars-fill":"bi-sun-fill");'
         . 'var m=document.getElementById("metaTheme");if(m)m.setAttribute("content",l?"#F4F6FB":"#0B1033");}'
         . 'sync();b.addEventListener("click",function(){var n=h.getAttribute("data-theme")==="light"?"dark":"light";'
         . 'h.classList.add("theme-anim");h.setAttribute("data-theme",n);try{localStorage.setItem("pubTheme",n)}catch(e){}sync();'
         . 'setTimeout(function(){h.classList.remove("theme-anim")},500);});})();</script>';
}

}
