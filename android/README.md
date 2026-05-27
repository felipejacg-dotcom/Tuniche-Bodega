# Aplicación Android — Tuniche Bodega (WebView wrapper)

Esta carpeta contiene la aplicación nativa Android que actúa como envoltura (WebView wrapper) para el sistema de control de bodega de EPP.

---

## 📍 Ubicación del Proyecto
La aplicación ha sido integrada directamente en el repositorio de desarrollo web para mantener el código unificado bajo el mismo control de versiones:
`C:\Users\Matrix\Desktop\PRUEBA1\Tuniche-Bodega\android`

---

## 🚀 Cómo abrir y compilar en Android Studio

1. Abre **Android Studio**.
2. Ve a **File ➡️ Open...** y selecciona la carpeta del proyecto en su nueva ubicación:
   `C:\Users\Matrix\Desktop\PRUEBA1\Tuniche-Bodega\android`
3. Si el IDE pregunta por la confianza del proyecto, haz clic en **Trust 'PRUEBA1' Folder**.
4. Para generar el APK de pruebas:
   * Ve al menú superior **Build ➡️ Build Bundle(s) / APK(s) ➡️ Build APK(s)**.
   * Al finalizar, haz clic en el enlace azul **locate** de la notificación inferior derecha para abrir el archivo `app-debug.apk`.

---

## 🛠️ Compilación reproducible desde Consola (PowerShell)
Para poder compilar la aplicación desde la terminal sin necesidad de abrir el IDE o depender de archivos locales no versionados (como `local.properties`), ejecuta los siguientes comandos en la terminal desde la raíz del proyecto web:

```powershell
# 1. Definir variables de entorno de Java y Android SDK
$env:JAVA_HOME="C:\Program Files\Android\Android Studio\jbr"
$env:ANDROID_HOME="C:\Users\Matrix\AppData\Local\Android\Sdk"

# 2. Entrar a la carpeta android
cd android

# 3. Compilar el APK debug
.\gradlew.bat :app:assembleDebug
```

El APK resultante se guardará en:
`android/app/build/outputs/apk/debug/app-debug.apk`

---

## 🔒 Endurecimiento y Seguridad Implementada
* **`android:allowBackup="false"`**: Deshabilitado en el `AndroidManifest.xml` para evitar fugas de datos y manipulación de cookies locales.
* **Restricción de Origen (Host Check)**: La aplicación de Android restringe estrictamente la navegación interna y las llamadas de la API nativa de puente (`playBeep`, `openNativeScanner`, `sharePdf`, `shareCierreTurnoPdf`) al dominio autorizado `https://tuniche-bodega.onrender.com/`. No se permite `http://` para el host productivo.
* **Compartir PDF nativo**: El cierre de turno se descarga desde Android con la cookie activa del WebView y luego se comparte con el selector nativo. Esto evita pasar PDFs grandes como Base64 por el puente JavaScript.
* **Enlaces externos controlados**: Los enlaces fuera del host autorizado solo se derivan al sistema si usan esquemas seguros conocidos (`https`, `mailto`, `tel`). Esquemas como `javascript`, `file`, `content` e `intent` quedan bloqueados dentro del WebView.
* **Deshabilitado de Acceso Local**: Se deshabilitó el acceso a archivos de contenido del dispositivo (`allowFileAccess = false` y `allowContentAccess = false`) desde la configuración del WebView.

---

## 📁 Archivos Excluidos de Git
Para mantener el repositorio limpio y evitar conflictos o subida accidental de credenciales, el archivo `.gitignore` raíz de la web excluye automáticamente los siguientes archivos de esta carpeta:
* Carpeta cache de compilación local: `android/.gradle/`
* Carpetas de configuración del IDE: `android/.idea/`
* Salidas de compilación locales: `android/build/` y `android/app/build/`
* Archivo de rutas locales del SDK: `android/local.properties`
* Archivos empaquetados APK/AAB y almacenes de claves (`.keystore` o `.jks`).
