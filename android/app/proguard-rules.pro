# Prevent obfuscation of @JavascriptInterface methods
-keepattributes JavascriptInterface
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Keep the WebAppInterface and its methods
-keep class com.tuniche.bodega.WebAppInterface {
    public *;
}

# Keep ML Kit scanner and related GMS classes
-keep class com.google.mlkit.** { *; }
-keep class com.google.android.gms.** { *; }
