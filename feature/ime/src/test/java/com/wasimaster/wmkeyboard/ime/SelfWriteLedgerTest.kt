package com.wasimaster.wmkeyboard.ime

import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SelfWriteLedgerTest {
    @After
    fun reset() = SelfWriteLedger.clear()

    @Test
    fun `a token is consumed once`() {
        SelfWriteLedger.record("a", now = 1_000)
        assertTrue(SelfWriteLedger.consume("a", now = 1_001))
        assertFalse(SelfWriteLedger.consume("a", now = 1_002))
    }

    @Test
    fun `a token expires after the ttl`() {
        SelfWriteLedger.record("a", now = 1_000)
        assertFalse(SelfWriteLedger.consume("a", now = 1_000 + SelfWriteLedger.DEFAULT_TTL_MILLIS + 1))
    }

    @Test
    fun `a missing token is false`() {
        assertFalse(SelfWriteLedger.consume(null))
        assertFalse(SelfWriteLedger.consume(""))
        assertFalse(SelfWriteLedger.consume("not-recorded"))
    }
}
