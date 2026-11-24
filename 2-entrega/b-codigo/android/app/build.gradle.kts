import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Firma de release: claves/firma.properties (archivo, alias, clave) — NO se sube a git. Sin ese archivo, solo debug.
val signing = Properties().apply {
    val f = rootProject.file("claves/firma.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "com.raphael.empresas.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.raphael.empresas.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 2
        versionName = "1.1.0"
        // dirección del servidor por defecto (se puede cambiar en la pantalla de entrada): -Pservidor=https://...
        buildConfigField("String", "DEFAULT_SERVER", "\"${project.findProperty("servidor") ?: ""}\"")
    }

    signingConfigs {
        if (signing.getProperty("archivo") != null) {
            create("release") {
                storeFile = rootProject.file("claves/" + signing.getProperty("archivo"))
                storePassword = signing.getProperty("clave")
                keyAlias = signing.getProperty("alias")
                keyPassword = signing.getProperty("clave")
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            manifestPlaceholders["cleartext"] = "true"     // en debug se puede probar contra http:// en la red local
        }
        release {
            isMinifyEnabled = false
            manifestPlaceholders["cleartext"] = "false"    // en release, solo https
            signingConfigs.findByName("release")?.let { signingConfig = it }
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.01.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.work:work-runtime-ktx:2.10.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
