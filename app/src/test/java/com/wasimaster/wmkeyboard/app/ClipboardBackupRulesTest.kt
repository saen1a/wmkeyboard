package com.wasimaster.wmkeyboard.app

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The clipboard history never travels in an Android OS backup. The secret
 * store is memory-only, and this rule is the second guard for a classifier
 * miss: even a wrongly classified clip cannot leave the device in a backup.
 */
class ClipboardBackupRulesTest {
    private val dataRules = File("src/main/res/xml/data_extraction_rules.xml").readText()
    private val legacyRules = File("src/main/res/xml/backup_rules.xml").readText()

    @Test
    fun `cloud backup and device transfer exclude the whole clipboard directory`() {
        assertEquals(2, Regex("""path="clipboard"""").findAll(dataRules).count())
        assertTrue(legacyRules.contains("""path="clipboard""""))
    }

    @Test
    fun `no clipboard subpath is included`() {
        assertFalse(dataRules.contains("""path="clipboard/""""))
        assertFalse(legacyRules.contains("""path="clipboard/""""))
    }
}
