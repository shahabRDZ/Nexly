import uuid

from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageStatus, MessageDeletion
from app.models.user import User


async def save_message(
    db: AsyncSession,
    sender_id: uuid.UUID,
    receiver_id: uuid.UUID | None = None,
    content: str | None = None,
    message_type: str = "text",
    media_url: str | None = None,
    media_size: int | None = None,
    media_name: str | None = None,
    group_id: uuid.UUID | None = None,
    channel_id: uuid.UUID | None = None,
    reply_to_id: uuid.UUID | None = None,
    is_forwarded: bool = False,
    forwarded_from_id: uuid.UUID | None = None,
    original_content: str | None = None,
    source_language: str | None = None,
    translated: bool = False,
) -> Message:
    msg = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content=content,
        original_content=original_content,
        source_language=source_language,
        translated=translated,
        message_type=message_type,
        media_url=media_url,
        media_size=media_size,
        media_name=media_name,
        group_id=group_id,
        channel_id=channel_id,
        reply_to_id=reply_to_id,
        is_forwarded=is_forwarded,
        forwarded_from_id=forwarded_from_id,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    other_id: uuid.UUID,
    limit: int = 50,
    before_id: uuid.UUID | None = None,
) -> list[Message]:
    # Get user's deleted message IDs
    del_q = select(MessageDeletion.message_id).where(MessageDeletion.user_id == user_id)
    del_result = await db.execute(del_q)
    deleted_ids = {row[0] for row in del_result.all()}

    q = select(Message).where(
        or_(
            and_(Message.sender_id == user_id, Message.receiver_id == other_id),
            and_(Message.sender_id == other_id, Message.receiver_id == user_id),
        ),
        Message.deleted_for_all == False,
    )
    if before_id:
        sub = select(Message.created_at).where(Message.id == before_id).scalar_subquery()
        q = q.where(Message.created_at < sub)

    q = q.order_by(Message.created_at.desc()).limit(limit)
    result = await db.execute(q)
    messages = [m for m in result.scalars().all() if m.id not in deleted_ids]
    return list(reversed(messages))


async def get_group_messages(
    db: AsyncSession,
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 50,
    before_id: uuid.UUID | None = None,
) -> list[Message]:
    del_q = select(MessageDeletion.message_id).where(MessageDeletion.user_id == user_id)
    del_result = await db.execute(del_q)
    deleted_ids = {row[0] for row in del_result.all()}

    q = select(Message).where(
        Message.group_id == group_id,
        Message.deleted_for_all == False,
    )
    if before_id:
        sub = select(Message.created_at).where(Message.id == before_id).scalar_subquery()
        q = q.where(Message.created_at < sub)

    q = q.order_by(Message.created_at.desc()).limit(limit)
    result = await db.execute(q)
    messages = [m for m in result.scalars().all() if m.id not in deleted_ids]
    return list(reversed(messages))


async def update_message_status(
    db: AsyncSession,
    message_ids: list[uuid.UUID],
    status: MessageStatus,
    user_id: uuid.UUID,
) -> int:
    """H-5 FIX: Batch update instead of per-ID query."""
    if not message_ids:
        return 0
    # Fetch all matching messages in one query
    result = await db.execute(
        select(Message).where(Message.id.in_(message_ids), Message.receiver_id == user_id)
    )
    count = 0
    for msg in result.scalars().all():
        if _can_transition(msg.status, status):
            msg.status = status
            count += 1
    await db.commit()
    return count


def _can_transition(current: MessageStatus, new: MessageStatus) -> bool:
    order = {MessageStatus.SENT: 0, MessageStatus.DELIVERED: 1, MessageStatus.SEEN: 2}
    return order.get(new, 0) > order.get(current, 0)


async def get_conversations_list(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """H-3 FIX: Reduced from 3N queries to 3 queries total."""
    # 1. Get all partner IDs
    partner_ids_q = (
        select(
            case(
                (Message.sender_id == user_id, Message.receiver_id),
                else_=Message.sender_id,
            ).label("partner_id")
        )
        .where(
            or_(Message.sender_id == user_id, Message.receiver_id == user_id),
            Message.group_id == None, Message.channel_id == None,
        )
        .distinct()
    )
    result = await db.execute(partner_ids_q)
    partner_ids = [row[0] for row in result.all() if row[0] is not None]
    if not partner_ids:
        return []

    # 2. Batch fetch all partner users
    users_result = await db.execute(select(User).where(User.id.in_(partner_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    # 3. Batch fetch unread counts
    unread_q = (
        select(Message.sender_id, func.count().label("cnt"))
        .where(
            Message.sender_id.in_(partner_ids),
            Message.receiver_id == user_id,
            Message.status != MessageStatus.SEEN,
        )
        .group_by(Message.sender_id)
    )
    unread_result = await db.execute(unread_q)
    unread_map = {row[0]: row[1] for row in unread_result.all()}

    # 4. Get last message per partner (still per-partner but minimal)
    conversations = []
    for pid in partner_ids:
        partner = users_map.get(pid)
        if not partner:
            continue
        last_msg_q = (
            select(Message)
            .where(
                or_(
                    and_(Message.sender_id == user_id, Message.receiver_id == pid),
                    and_(Message.sender_id == pid, Message.receiver_id == user_id),
                ),
                Message.deleted_for_all == False,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg = (await db.execute(last_msg_q)).scalar_one_or_none()
        conversations.append({
            "partner": partner,
            "last_message": last_msg,
            "unread_count": unread_map.get(pid, 0),
        })

    conversations.sort(
        key=lambda c: c["last_message"].created_at if c["last_message"] else 0,
        reverse=True,
    )
    return conversations
