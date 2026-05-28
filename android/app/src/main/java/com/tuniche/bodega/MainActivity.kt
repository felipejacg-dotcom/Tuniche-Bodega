package com.tuniche.bodega

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.media.ToneGenerator
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.webkit.JavascriptInterface
import android.webkit.CookieManager
import android.webkit.PermissionRequest
import android.webkit.WebResourceRequest
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
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

private const val ALLOWED_ORIGIN = "https://tuniche-bodega.onrender.com"
private const val ALLOWED_HOST = "tuniche-bodega.onrender.com"
private const val CIERRE_PDF_PATH = "/api/cierre_turno/pdf"

private fun isAllowedAppUrl(url: String?): Boolean {
    val parsed = runCatching { Uri.parse(url ?: "") }.getOrNull() ?: return false
    return parsed.scheme == "https" && parsed.host == ALLOWED_HOST
}

private fun isAllowedExternalUrl(url: String?): Boolean {
    val parsed = runCatching { Uri.parse(url ?: "") }.getOrNull() ?: return false
    return parsed.scheme in setOf("https", "mailto", "tel")
}

private fun sanitizePdfFilename(filename: String): String {
    val cleaned = filename.replace(Regex("[^A-Za-z0-9._-]"), "_").trim('_')
    val withFallback = cleaned.ifBlank { "cierre-turno.pdf" }
    return if (withFallback.endsWith(".pdf", ignoreCase = true)) withFallback else "$withFallback.pdf"
}

class WebAppInterface(private val mContext: Context) {
    private var toneGen: ToneGenerator = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 100)

    // Validar el origen del WebView antes de ejecutar cualquier accion nativa
    private fun checkSecureOrigin(): Boolean {
        val activity = mContext as? AppCompatActivity ?: return false
        val webView = activity.findViewById<WebView>(R.id.webView) ?: return false
        return isAllowedAppUrl(webView.url)
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

        val duration = if (type == "success") 100L else 300L
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(VibrationEffect.createOneShot(duration, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(duration)
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
    fun sharePdf(base64Data: String?, filename: String, tipoTurno: String?, desde: String?, hasta: String?) {
        val activity = mContext as? AppCompatActivity ?: return
        activity.runOnUiThread {
            val webView = activity.findViewById<WebView>(R.id.webView)
            if (!isAllowedAppUrl(webView?.url)) return@runOnUiThread

            if (!base64Data.isNullOrBlank()) {
                // Compartido instantáneo usando Base64
                thread(name = "pdf-base64-decode") {
                    try {
                        val pdfBytes = android.util.Base64.decode(base64Data, android.util.Base64.DEFAULT)
                        val file = writePdfToCache(pdfBytes, filename)
                        activity.runOnUiThread {
                            try {
                                openPdfShareSheet(file)
                            } catch (e: Exception) {
                                showShareError(activity, e)
                            }
                        }
                    } catch (e: Exception) {
                        activity.runOnUiThread { showShareError(activity, e) }
                    }
                }
            } else {
                // Descarga nativa en segundo plano como fallback
                thread(name = "pdf-native-download") {
                    try {
                        val queryParams = StringBuilder()
                        if (!tipoTurno.isNullOrBlank()) {
                            queryParams.append("tipo_turno=").append(Uri.encode(tipoTurno))
                        }
                        if (!desde.isNullOrBlank()) {
                            if (queryParams.isNotEmpty()) queryParams.append("&")
                            queryParams.append("desde=").append(Uri.encode(desde))
                        }
                        if (!hasta.isNullOrBlank()) {
                            if (queryParams.isNotEmpty()) queryParams.append("&")
                            queryParams.append("hasta=").append(Uri.encode(hasta))
                        }
                        val pdfUrl = if (queryParams.isNotEmpty()) {
                            "$ALLOWED_ORIGIN$CIERRE_PDF_PATH?$queryParams"
                        } else {
                            "$ALLOWED_ORIGIN$CIERRE_PDF_PATH"
                        }

                        val connection = (URL(pdfUrl).openConnection() as HttpURLConnection).apply {
                            requestMethod = "GET"
                            connectTimeout = 15000
                            readTimeout = 30000
                            val cookies = CookieManager.getInstance().getCookie(ALLOWED_ORIGIN)
                            if (!cookies.isNullOrBlank()) {
                                setRequestProperty("Cookie", cookies)
                            }
                        }

                        val code = connection.responseCode
                        if (code !in 200..299) {
                            throw IllegalStateException("HTTP $code al descargar PDF")
                        }

                        val bytes = connection.inputStream.use { it.readBytes() }
                        val file = writePdfToCache(bytes, filename)
                        activity.runOnUiThread {
                            try {
                                openPdfShareSheet(file)
                            } catch (e: Exception) {
                                showShareError(activity, e)
                            }
                        }
                    } catch (e: Exception) {
                        activity.runOnUiThread { showShareError(activity, e) }
                    }
                }
            }
        }
    }

    private fun writePdfToCache(pdfBytes: ByteArray, filename: String): File {
        val file = File(mContext.cacheDir, sanitizePdfFilename(filename))
        FileOutputStream(file).use { fos -> fos.write(pdfBytes) }
        return file
    }

    private fun openPdfShareSheet(file: File) {
        val fileUri = androidx.core.content.FileProvider.getUriForFile(
            mContext,
            "com.tuniche.bodega.fileprovider",
            file
        )

        val shareIntent = Intent().apply {
            action = Intent.ACTION_SEND
            putExtra(Intent.EXTRA_STREAM, fileUri)
            type = "application/pdf"
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }

        mContext.startActivity(Intent.createChooser(shareIntent, "Compartir Cierre de Turno"))
    }

    private fun showShareError(activity: AppCompatActivity, e: Exception) {
        val webView = activity.findViewById<WebView>(R.id.webView)
        val safeError = e.message?.replace("'", "\\'")?.replace("\n", "") ?: "Error al compartir"
        webView?.evaluateJavascript(
            "javascript:if(typeof toast === 'function') { toast('Error al compartir PDF: $safeError', 'error'); } else { alert('Error al compartir PDF: $safeError'); }",
            null
        )
        Toast.makeText(mContext, "Error al compartir PDF: $safeError", Toast.LENGTH_LONG).show()
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
        webSettings.cacheMode = WebSettings.LOAD_DEFAULT // Permite usar la caché local para velocidad, con cache-busting en HTML
        webSettings.databaseEnabled = true
        webSettings.mediaPlaybackRequiresUserGesture = false

        // Forzar aceleración por hardware para suavizar animaciones y rendimiento de dibujado
        webView.setLayerType(android.view.View.LAYER_TYPE_HARDWARE, null)

        // Deshabilitar acceso a archivos locales para endurecer seguridad
        webSettings.allowFileAccess = false
        webSettings.allowContentAccess = false

        // Restringir navegación estrictamente al dominio autorizado
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val url = request?.url?.toString() ?: ""
                // Permitir navegacion solo si es el host de produccion por HTTPS.
                if (isAllowedAppUrl(url)) {
                    return false // Permite la navegación dentro del WebView
                }

                if (isAllowedExternalUrl(url)) {
                    try {
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                        startActivity(intent)
                    } catch (e: Exception) {
                        Toast.makeText(this@MainActivity, "No se puede abrir enlace externo", Toast.LENGTH_SHORT).show()
                    }
                } else {
                    Toast.makeText(this@MainActivity, "Enlace bloqueado por seguridad", Toast.LENGTH_SHORT).show()
                }
                return true // Bloquea la navegación dentro del WebView
            }

            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: android.webkit.WebResourceError?) {
                super.onReceivedError(view, request, error)
                // Solo reintentar para la carga de la página principal (main frame)
                if (request?.isForMainFrame == true) {
                    val errorCode = error?.errorCode
                    // Reintentar si es error de conexión, timeout o DNS
                    if (errorCode == WebViewClient.ERROR_CONNECT || errorCode == WebViewClient.ERROR_TIMEOUT || errorCode == WebViewClient.ERROR_HOST_LOOKUP) {
                        runOnUiThread {
                            // Limpiamos caché ante error de red para asegurar recarga limpia
                            view?.clearCache(true)
                            Toast.makeText(this@MainActivity, "Conexión lenta o fallida. Reintentando...", Toast.LENGTH_SHORT).show()
                            view?.postDelayed({
                                view.loadUrl("$ALLOWED_ORIGIN/")
                            }, 4000)
                        }
                    }
                }
            }

            override fun onRenderProcessGone(view: WebView?, detail: android.webkit.RenderProcessGoneDetail?): Boolean {
                // Si el proceso de renderizado del WebView se destruye (pantalla negra), recargamos
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "Recuperando pantalla...", Toast.LENGTH_SHORT).show()
                    view?.loadUrl("$ALLOWED_ORIGIN/")
                }
                return true // Retornar true evita que la aplicación se cierre (crash)
            }
        }

        // Agregar la interfaz JS para el puente de comunicación nativo
        webView.addJavascriptInterface(WebAppInterface(this), "AndroidApp")

        webView.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                runOnUiThread {
                    val originAllowed = request.origin?.toString()?.trimEnd('/') == ALLOWED_ORIGIN
                    val cameraResources = request.resources.filter {
                        it == PermissionRequest.RESOURCE_VIDEO_CAPTURE
                    }.toTypedArray()

                    if (originAllowed && cameraResources.isNotEmpty()) {
                        request.grant(cameraResources)
                    } else {
                        request.deny()
                    }
                }
            }
        }

        // Pedir permiso nativamente a Android inicialmente al abrir (Esto habilitará el hardware en Android)
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), CAMERA_PERMISSION_CODE)
        }

        // Limpiar la caché solo ante cambio de versión de la aplicación
        val sharedPrefs = getSharedPreferences("AppPrefs", MODE_PRIVATE)
        val lastVersionCode = sharedPrefs.getInt("last_version_code", -1)
        val currentVersionCode = try {
            val pInfo = packageManager.getPackageInfo(packageName, 0)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                pInfo.longVersionCode.toInt()
            } else {
                @Suppress("DEPRECATION")
                pInfo.versionCode
            }
        } catch (e: Exception) {
            1
        }
        if (currentVersionCode != lastVersionCode) {
            webView.clearCache(true)
            sharedPrefs.edit().putInt("last_version_code", currentVersionCode).apply()
        }

        // Carga la URL oficial de producción
        webView.loadUrl("$ALLOWED_ORIGIN/")

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
