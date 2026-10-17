"""
likby.repositories.sqlite.referral_reward_repository
aiosqlite implementation of ReferralRewardRepository.
"""

from datetime import datetime
from typing import List, Optional
import aiosqlite
from likby.domain.entities.referral import ReferralReward
from likby.domain.enums import ReferralQualificationStatus, ReferralRewardStatus
from likby.repositories.interfaces import ReferralRewardRepository


class SqliteReferralRewardRepository(ReferralRewardRepository):
    """SQLite referral reward tracking and abuse prevention repository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, referral: ReferralReward) -> None:
        await self._conn.execute(
            """
            INSERT INTO referral_rewards (
                id, referrer_user_id, invited_user_id, qualification_status,
                reward_status, reward_entitlement_id, qualified_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(invited_user_id) DO UPDATE SET
                qualification_status = excluded.qualification_status,
                reward_status = excluded.reward_status,
                reward_entitlement_id = excluded.reward_entitlement_id,
                qualified_at = excluded.qualified_at
            """,
            (
                referral.id,
                referral.referrer_user_id,
                referral.invited_user_id,
                referral.qualification_status.value,
                referral.reward_status.value,
                referral.reward_entitlement_id,
                referral.qualified_at.isoformat() if referral.qualified_at else None,
                referral.created_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_by_invited_user_id(self, invited_user_id: str) -> Optional[ReferralReward]:
        async with self._conn.execute(
            "SELECT id, referrer_user_id, invited_user_id, qualification_status, reward_status, reward_entitlement_id, qualified_at, created_at "
            "FROM referral_rewards WHERE invited_user_id = ?",
            (invited_user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_entity(row) if row else None

    async def count_qualified_in_period(self, referrer_user_id: str, since: str) -> int:
        async with self._conn.execute(
            "SELECT COUNT(*) FROM referral_rewards WHERE referrer_user_id = ? AND reward_status = 'REWARDED' AND qualified_at >= ?",
            (referrer_user_id, since),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_user_referrals(self, referrer_user_id: str) -> List[ReferralReward]:
        referrals = []
        async with self._conn.execute(
            "SELECT id, referrer_user_id, invited_user_id, qualification_status, reward_status, reward_entitlement_id, qualified_at, created_at "
            "FROM referral_rewards WHERE referrer_user_id = ? ORDER BY created_at DESC",
            (referrer_user_id,),
        ) as cursor:
            async for row in cursor:
                referrals.append(self._row_to_entity(row))
        return referrals

    def _row_to_entity(self, row: tuple) -> ReferralReward:
        return ReferralReward(
            id=row[0],
            referrer_user_id=row[1],
            invited_user_id=row[2],
            qualification_status=ReferralQualificationStatus(row[3]),
            reward_status=ReferralRewardStatus(row[4]),
            reward_entitlement_id=row[5],
            qualified_at=datetime.fromisoformat(row[6]) if row[6] else None,
            created_at=datetime.fromisoformat(row[7]),
        )
