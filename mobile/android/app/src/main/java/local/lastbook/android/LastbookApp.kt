package local.lastbook.android

import android.app.Application
import local.lastbook.core.LastbookCore

class LastbookApp : Application() {
    override fun onCreate() {
        super.onCreate()
        LastbookCore.init(this)
    }
}
