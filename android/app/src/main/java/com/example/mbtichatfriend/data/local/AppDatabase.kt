package com.example.mbtichatfriend.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [MessageEntity::class, CharacterEntity::class, DiaryEntity::class, MemoryEntity::class],
    version = 4,
    exportSchema = true
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun messageDao(): MessageDao
    abstract fun characterDao(): CharacterDao
    abstract fun diaryDao(): DiaryDao
    abstract fun memoryDao(): MemoryDao

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
    }
}
