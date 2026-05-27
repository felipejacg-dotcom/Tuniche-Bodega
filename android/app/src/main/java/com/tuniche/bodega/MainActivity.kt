package com.tuniche.bodega

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions

class WebAppInterface(private val mContext: Context) {
    private var toneGen: ToneGenerator = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 100)

    // Validar el origen del WebView antes de ejecutar cualquier acción nativa
    private fun checkSecureOrigin(): Boolean {
        val activity = mContext as? AppCompatActivity ?: return false
        val webView = activity.findViewById<WebView>(R.id.webView) ?: return false
        val url = webView.url ?: ""
        return url.startsWith("https://tuniche-bodega.onrender.com/") || url.startsWith("http://tuniche-bodega.onrender.com/")
    }

    @JavascriptInterface
    fun playBeep(type: String) {
        if (!checkSecureOrigin()) return

        // Sonido
        if (type == "success") {
            toneGen.startTone(ToneGenerator.TONE_PROP_BEEP, 100)
        } else {
            toneGen.startTone(ToneGenerator.TONE_SUP_ERROR, 300)
        }

        // Vibración
        val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vibratorManager = mContext.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            vibratorManager.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            mContext.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }

        if (type == "success") {
            vibrator.vibrate(VibrationEffect.createOneShot(100, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            vibrator.vibrate(VibrationEffect.createOneShot(300, VibrationEffect.DEFAULT_AMPLITUDE))
        }
    }

    @JavascriptInterface
    fun openNativeScanner(type: String) {
        if (!checkSecureOrigin()) return

        val activity = mContext as AppCompatActivity
        activity.runOnUiThread {
            val options = GmsBarcodeScannerOptions.Builder().build()
            val scanner = GmsBarcodeScanning.getClient(activity, options)

            scanner.startScan()
                .addOnSuccessListener { barcode ->
                    val rawValue = barcode.rawValue ?: ""
                    val safeValue = rawValue.replace("'", "\\'").replace("\n", "").replace("\r", "")
                    val webView = activity.findViewById<WebView>(R.id.webView)
                    webView.evaluateJavascript("javascript:window.onNativeScanResult('$safeValue', '$type');", null)
                }
                .addOnCanceledListener {
                    // Acción de cancelación si fuera necesario
                }
                .addOnFailureListener { e ->
                    val webView = activity.findViewById<WebView>(R.id.webView)
                    val safeError = e.message?.replace("'", "\\'")?.replace("\n", "") ?: "Error"
                    // Enviar callback de error a la UI web usando el toast nativo si es posible, fallback a alert
                    webView.evaluateJavascript(
                        "javascript:if(typeof toast === 'function') { toast('Error cámara nativa: $safeError', 'error'); } else { alert('Error cámara nativa: $safeError'); }",
                        null
                    )
                    Toast.makeText(mContext, "Error cámara nativa: $safeError", Toast.LENGTH_LONG).show()
                }
        }
    }

    @JavascriptInterface
    fun sharePdf(base64Data: String, filename: String) {
        if (!checkSecureOrigin()) return

        val activity = mContext as AppCompatActivity
        activity.runOnUiThread {
            try {
                // Decodificar los bytes del PDF desde Base64
                val pdfBytes = android.util.Base64.decode(base64Data, android.util.Base64.DEFAULT)
                
                // Guardar en la carpeta cache temporal de la app
                val cacheDir = mContext.cacheDir
                val file = java.io.File(cacheDir, filename)
                java.io.FileOutputStream(file).use { fos ->
                    fos.write(pdfBytes)
                }

                // Generar URI seguro usando el FileProvider
                val fileUri = androidx.core.content.FileProvider.getUriForFile(
                    mContext,
                    "com.tuniche.bodega.fileprovider",
                    file
                )

                // Crear el Intent nativo de compartir
                val shareIntent = android.content.Intent().apply {
                    action = android.content.Intent.ACTION_SEND
                    putExtra(android.content.Intent.EXTRA_STREAM, fileUri)
                    type = "application/pdf"
                    addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                
                // Abrir selector nativo (WhatsApp, Gmail, etc.)
                mContext.startActivity(android.content.Intent.createChooser(shareIntent, "Compartir Cierre de Turno"))
            } catch (e: Exception) {
                val webView = activity.findViewById<WebView>(R.id.webView)
                val safeError = e.message?.replace("'", "\\'")?.replace("\n", "") ?: "Error al compartir"
                webView.evaluateJavascript(
                    "javascript:if(typeof toast === 'function') { toast('Error al compartir PDF: $safeError', 'error'); } else { alert('Error al compartir PDF: $safeError'); }",
                    null
                )
                Toast.makeText(mContext, "Error al compartir PDF: $safeError", Toast.LENGTH_LONG).show()
            }
        }
    }
}

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val CAMERA_PERMISSION_CODE = 100

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)

        val webSettings: WebSettings = webView.settings
        webSettings.javaScriptEnabled = true
        webSettings.domStorageEnabled = true
        webSettings.cacheMode = WebSettings.LOAD_NO_CACHE // Forzar actualización siempre
        webSettings.mediaPlaybackRequiresUserGesture = false

        // Deshabilitar acceso a archivos locales para endurecer seguridad
        webSettings.allowFileAccess = false
        webSettings.allowContentAccess = false

        // Restringir navegación estrictamente al dominio autorizado
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: android.webkit.WebResourceRequest?): Boolean {
                val url = request?.url?.toString() ?: ""
                // Permitir navegación solo si es el host de producción
                if (url.startsWith("https://tuniche-bodega.onrender.com/") || url.startsWith("http://tuniche-bodega.onrender.com/")) {
                    return false // Permite la navegación dentro del WebView
                }
                // Si es un enlace externo, abrirlo en el navegador del sistema para seguridad
                try {
                    val intent = android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url))
                    startActivity(intent)
                } catch (e: Exception) {
                    Toast.makeText(this@MainActivity, "No se puede abrir enlace externo", Toast.LENGTH_SHORT).show()
                }
                return true // Bloquea la navegación dentro del WebView
            }
        }

        // Agregar la interfaz JS para el puente de comunicación nativo
        webView.addJavascriptInterface(WebAppInterface(this), "AndroidApp")

        webView.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                // Conceder permisos de cámara al WebView
                runOnUiThread {
                    request.grant(request.resources)
                }
            }
        }

        // Pedir permiso nativamente a Android inicialmente al abrir (Esto habilitará el hardware en Android)
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), CAMERA_PERMISSION_CODE)
        }

        // Carga la URL oficial de producción
        webView.loadUrl("https://tuniche-bodega.onrender.com/")

        // Manejo del botón atrás moderno
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })
    }
}
