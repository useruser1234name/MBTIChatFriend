package com.example.mbtichatfriend.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [MessageEntity::class, CharacterEntity::class, DiaryEntity::class, MemoryEntity::class, FeedbackEntity::class],
    version = 8,
    exportSchema = true
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun messageDao(): MessageDao
    abstract fun characterDao(): CharacterDao
    abstract fun diaryDao(): DiaryDao
    abstract fun memoryDao(): MemoryDao
    abstract fun feedbackDao(): FeedbackDao

    companion object {
        /** v1 → v2: characters 테이블에 avatarId 컬럼 추가 */
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "ALTER TABLE characters ADD COLUMN avatarId TEXT NOT NULL DEFAULT 'default'"
                )
            }
        }

        /** v2 → v3: diaries 테이블 추가 */
        val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """CREATE TABLE IF NOT EXISTS diaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                        characterId INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        emotion TEXT NOT NULL DEFAULT 'NEUTRAL',
                        date TEXT NOT NULL,
                        createdAt INTEGER NOT NULL
                    )"""
                )
            }
        }

        /** v3 → v4: memories 테이블 추가 */
        val MIGRATION_3_4 = object : Migration(3, 4) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                        characterId INTEGER NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        createdAt INTEGER NOT NULL
                    )"""
                )
            }
        }

        /** v4 → v5: messages 테이블에 sendStatus, retryCount 컬럼 추가 */
        val MIGRATION_4_5 = object : Migration(4, 5) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE messages ADD COLUMN sendStatus TEXT NOT NULL DEFAULT 'SENT'")
                db.execSQL("ALTER TABLE messages ADD COLUMN retryCount INTEGER NOT NULL DEFAULT 0")
            }
        }

        /** v5 → v6: characters 테이블에 expressionSet, expressionSetReady 컬럼 추가 */
        val MIGRATION_5_6 = object : Migration(5, 6) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE characters ADD COLUMN expressionSet TEXT DEFAULT NULL")
                db.execSQL("ALTER TABLE characters ADD COLUMN expressionSetReady INTEGER NOT NULL DEFAULT 0")
            }
        }

        /** v6 → v7: feedback 테이블 추가 */
        val MIGRATION_6_7 = object : Migration(6, 7) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """CREATE TABLE IF NOT EXISTS feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                        messageId INTEGER NOT NULL,
                        characterId INTEGER NOT NULL,
                        feedbackType TEXT NOT NULL,
                        synced INTEGER NOT NULL DEFAULT 0,
                        createdAt INTEGER NOT NULL
                    )"""
                )
            }
        }

        /** v7 → v8: feedback 테이블에 roomId 컬럼 추가 (room_id 미전달 결함 수정) */
        val MIGRATION_7_8 = object : Migration(7, 8) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE feedback ADD COLUMN roomId TEXT NOT NULL DEFAULT ''")
            }
        }
    }
}
