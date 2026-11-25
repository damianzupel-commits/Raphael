package com.raphael.empresas.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.core.content.ContextCompat
import com.raphael.empresas.app.ui.RaphaelApp
import com.raphael.empresas.app.ui.RaphaelTheme

class MainActivity : ComponentActivity() {
    private val vm: AppViewModel by viewModels()
    private val askNotifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        vm.onPairLink(intent.dataString)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        PendingWorker.ensureChannel(this)
        vm.onPairLink(intent?.dataString)
        when (intent?.getStringExtra("tab")) {
            "pending" -> vm.tab = Tab.PENDIENTES
            "more" -> vm.tab = Tab.MAS
        }
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (vm.loggedIn) {
            PendingWorker.schedule(this)
            vm.refreshAll()
        }
        setContent { RaphaelTheme { RaphaelApp(vm) } }
    }
}
