package com.raphael.empresas.app

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

/**
 * Cada ~15 minutos (lo mínimo que permite Android) pregunta al servidor si hay pendientes nuevos y avisa en el celular.
 * Sin Firebase ni terceros: solo la API de la instalación. Pendiente para la 03: push instantáneo.
 */
class PendingWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val prefs = Prefs(applicationContext)
        if (!prefs.loggedIn) return Result.success()
        return try {
            val u = prefs.api().updates()
            if (u.latest > prefs.lastNotified && u.pending > 0) {
                notify(applicationContext, u)
                prefs.lastNotified = u.latest
            }
            if (u.noticesUnseen > 0 && u.noticeLatest > prefs.lastNotice) {
                notifyNotice(applicationContext, u)
                prefs.lastNotice = u.noticeLatest
            }
            Result.success()
        } catch (e: ApiError) {
            if (e.unauthorized) prefs.clearSession()
            Result.success()          // sin conexión: se vuelve a intentar en el próximo turno
        }
    }

    companion object {
        private const val WORK = "pendientes"
        const val CHANNEL = "pendientes"

        fun schedule(context: Context) {
            val req = PeriodicWorkRequestBuilder<PendingWorker>(15, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(WORK, ExistingPeriodicWorkPolicy.KEEP, req)
        }

        fun cancel(context: Context) = WorkManager.getInstance(context).cancelUniqueWork(WORK)

        fun ensureChannel(context: Context) {
            val ch = NotificationChannel(CHANNEL, context.getString(R.string.channel_pending), NotificationManager.IMPORTANCE_DEFAULT)
            ch.description = context.getString(R.string.channel_pending_desc)
            context.getSystemService(NotificationManager::class.java).createNotificationChannel(ch)
        }

        fun notifyNotice(context: Context, u: Updates) {
            if (Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
            ) return
            ensureChannel(context)
            val open = PendingIntent.getActivity(context, 1, Intent(context, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                .putExtra("tab", "more"), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            val title = if (u.noticesUnseen == 1) "Raphael te dejó un aviso" else "Raphael te dejó ${u.noticesUnseen} avisos"
            val n = NotificationCompat.Builder(context, CHANNEL)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(title)
                .setContentText(u.noticeLast)
                .setStyle(NotificationCompat.BigTextStyle().bigText(u.noticeLast))
                .setContentIntent(open)
                .setAutoCancel(true)
                .build()
            try {
                NotificationManagerCompat.from(context).notify(2, n)
            } catch (e: SecurityException) {
                // sin permiso de notificaciones: no se avisa
            }
        }

        fun notify(context: Context, u: Updates) {
            if (Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
            ) return
            ensureChannel(context)
            val open = PendingIntent.getActivity(context, 0, Intent(context, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                .putExtra("tab", "pending"), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            val title = if (u.pending == 1) "Tenés 1 cosa para decidir" else "Tenés ${u.pending} cosas para decidir"
            val text = u.items.lastOrNull() ?: "Abrí Raphael para verlas"
            val n = NotificationCompat.Builder(context, CHANNEL)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(NotificationCompat.BigTextStyle().bigText(u.items.takeLast(3).joinToString("\n")))
                .setContentIntent(open)
                .setAutoCancel(true)
                .build()
            try {
                NotificationManagerCompat.from(context).notify(1, n)
            } catch (e: SecurityException) {
                // sin permiso de notificaciones: no se avisa
            }
        }
    }
}
