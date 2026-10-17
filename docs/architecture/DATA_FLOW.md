# LikBy Data Flow & Sequence Diagrams

---

## 1. Media Upload & Protected Relay Flow

This diagram illustrates how an uploaded photo/video is verified against quotas, archived, and relayed to a chat partner with content protection.

```mermaid
sequenceDiagram
    autonumber
    actor Alice as User A (Uploader)
    participant TG as Telegram Bot API
    participant Relay as ChatRelayService
    participant Quota as MediaQuotaService
    participant Store as MediaStorage (Local / R2)
    actor Bob as User B (Recipient)

    Alice->>TG: Sends Photo/Video in Active Session
    TG->>Relay: Ingest Update (file_id, size)
    
    Relay->>Quota: check_and_reserve_upload(Alice.id, size)
    alt Upload Quota Exceeded or Oversized
        Quota-->>Relay: QuotaExceededException
        Relay-->>TG: Inform Alice with Upgrade / Reset Info
    else Upload Approved
        Quota-->>Relay: Reservation Token (Upload)
        Relay->>Quota: check_and_reserve_receive(Bob.id)
        alt Bob Receive Quota Exceeded
            Quota-->>Relay: QuotaExceededException
            Relay->>Quota: rollback_upload_reservation(Alice.id)
            Relay-->>TG: Inform Alice that Bob reached daily receive limit
        else Both Approved
            Quota-->>Relay: Reservation Token (Receive)
            par Async Archival
                Relay->>Store: Archive binary via SHA-256 key
            and Telegram Native Relay
                Relay->>TG: send_photo(Bob.id, file_id, protect_content=True)
            end
            alt Relay Succeeded
                Relay->>Quota: commit_reservations(Alice.id, Bob.id)
                Relay-->>Alice: Delivery Checkmark
            else Relay Failed (Network / Blocked)
                Relay->>Quota: rollback_reservations(Alice.id, Bob.id)
                Relay-->>Alice: Relay Failure Notification
            end
        end
    end
```

---

## 2. Matchmaking & Mutual Like Flow

```mermaid
sequenceDiagram
    autonumber
    actor Alice as User A
    participant Handler as DiscoveryHandler
    participant Social as SocialService
    participant DB as Relational Database
    actor Bob as User B

    Alice->>Handler: Likes Bob's Profile
    Handler->>Social: register_like(Alice.id, Bob.id)
    Social->>DB: Check reciprocal like (Bob -> Alice)
    alt No Reciprocal Like
        Social->>DB: Record like(Alice, Bob)
        Social-->>Handler: Like Registered
    else Mutual Like Found!
        Social->>DB: Create Match Record & Mutual Friendship
        Social->>DB: Check Friend Capacities (Base: max 3)
        Social-->>Handler: Match Created!
        par Notify Alice
            Social->>Alice: "It's a Match! Meet your new connection."
        and Notify Bob
            Social->>Bob: "It's a Match! You have connected with a new friend."
        end
    end
```
