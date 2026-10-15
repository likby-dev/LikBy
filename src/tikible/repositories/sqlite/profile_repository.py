"""
tikible.repositories.sqlite.profile_repository
aiosqlite implementation of ProfileRepository.
"""

from datetime import datetime
import json
from typing import Optional
import aiosqlite
from tikible.domain.entities.profile import Profile
from tikible.domain.enums import Gender, GenderPreference
from tikible.repositories.interfaces import ProfileRepository


class SqliteProfileRepository(ProfileRepository):
    """SQLite implementation of ProfileRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def get_by_user_id(self, user_id: str) -> Optional[Profile]:
        async with self._conn.execute(
            """
            SELECT user_id, display_name, age, gender, bio, location_country,
                   location_city, languages, interests, preferred_gender_filter,
                   min_age_filter, max_age_filter, created_at, updated_at
            FROM profiles WHERE user_id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def save(self, profile: Profile) -> None:
        await self._conn.execute(
            """
            INSERT INTO profiles (
                user_id, display_name, age, gender, bio, location_country,
                location_city, languages, interests, preferred_gender_filter,
                min_age_filter, max_age_filter, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name = excluded.display_name,
                age = excluded.age,
                gender = excluded.gender,
                bio = excluded.bio,
                location_country = excluded.location_country,
                location_city = excluded.location_city,
                languages = excluded.languages,
                interests = excluded.interests,
                preferred_gender_filter = excluded.preferred_gender_filter,
                min_age_filter = excluded.min_age_filter,
                max_age_filter = excluded.max_age_filter,
                updated_at = excluded.updated_at
            """,
            (
                profile.user_id,
                profile.display_name,
                profile.age,
                profile.gender.value,
                profile.bio,
                profile.location_country,
                profile.location_city,
                json.dumps(profile.languages),
                json.dumps(profile.interests),
                json.dumps([p.value for p in profile.preferred_gender_filter]),
                profile.min_age_filter,
                profile.max_age_filter,
                profile.created_at.isoformat(),
                profile.updated_at.isoformat(),
            ),
        )
        await self._conn.commit()

    def _row_to_entity(self, row: tuple) -> Profile:
        return Profile(
            user_id=row[0],
            display_name=row[1],
            age=row[2],
            gender=Gender(row[3]),
            bio=row[4],
            location_country=row[5],
            location_city=row[6],
            languages=json.loads(row[7]),
            interests=json.loads(row[8]),
            preferred_gender_filter=[GenderPreference(p) for p in json.loads(row[9])],
            min_age_filter=row[10],
            max_age_filter=row[11],
            created_at=datetime.fromisoformat(row[12]),
            updated_at=datetime.fromisoformat(row[13]),
        )
