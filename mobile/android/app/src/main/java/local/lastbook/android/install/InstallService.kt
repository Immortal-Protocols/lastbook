package local.lastbook.android.install

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import local.lastbook.android.MainActivity
import local.lastbook.android.R

/** Keeps an install alive while Lastbook is in the background, with a visible progress notification. */
class InstallService : Service() {
    companion object {
        const val CHANNEL = "lastbook-install"
        const val NOTIFICATION_ID = 41

        fun start(context: Context) {
            val i = Intent(context, InstallService::class.java)
            if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(i) else context.startService(i)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, InstallService::class.java))
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val nm = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(NotificationChannel(CHANNEL, "Downloads", NotificationManager.IMPORTANCE_LOW))
        }
        val open = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        val openPi = PendingIntent.getActivity(this, 0, open,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val n: Notification = NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("Installing Lastbook")
            .setContentText("Downloading and checking the library. This continues while Lastbook is in the background.")
            .setContentIntent(openPi)
            .setOngoing(true)
            .setProgress(0, 0, true)
            .build()
        startForeground(NOTIFICATION_ID, n)
        return START_NOT_STICKY
    }
}
