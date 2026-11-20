package local.lastbook.android.data

import local.lastbook.core.LastbookCore

object Services {
    val chat: ChatStore by lazy { ChatStore(LastbookCore.context) }
    val progress: VideoProgress by lazy { VideoProgress(LastbookCore.context) }
}
