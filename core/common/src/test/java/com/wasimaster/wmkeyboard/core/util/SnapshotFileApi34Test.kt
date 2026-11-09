package com.wasimaster.wmkeyboard.core.util

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * The plain JVM test sees `Build.VERSION.SDK_INT == 0` and exercises the
 * API-24/25 rename fallback. This API-34 run exercises the `java.nio.file`
 * branch that real Android 8+ devices take.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class SnapshotFileApi34Test {
    @get:Rule
    val temp = TemporaryFolder()

    @Test
    fun api34WritesThroughFilesMove() {
        val target = File(temp.root, "learning/store.json")
        SnapshotFile.writeAtomically(target, "api34")
        assertEquals("api34", target.readText())
        assertEquals(0, target.parentFile.listFiles { file -> file.name.endsWith(".part") }.orEmpty().size)
    }
}
