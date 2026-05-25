BASELINE_DIAGRAM = """
graph LR
    A[Your Application] -->|Direct API Call| B[Groq LLM]
    B -->|Response| A
"""

ROUTING_DIAGRAM = """
graph LR
    A[Your Application] -->|Request| B[Portkey Gateway]
    B -->|Forwarded Request| C[Groq LLM]
    C -->|Response| B
    B -->|Response| A
    B -.->|Auto-logs tokens cost latency| D[Portkey Dashboard]
"""

METADATA_DIAGRAM = """
graph LR
    A[Your App] -->|Request plus Metadata Tags| B[Portkey Gateway]
    B -->|Forward| C[Groq LLM]
    B -->|user session feature env tags| D[Portkey Dashboard]
    D -->|Filter and Analyze| E[Usage Analytics]
"""

RETRY_DIAGRAM = """
sequenceDiagram
    participant App
    participant Portkey
    participant LLM
    App->>Portkey: Send Request
    Portkey->>LLM: Attempt 1
    LLM-->>Portkey: 429 Rate Limited
    Note over Portkey: Wait 1s backoff
    Portkey->>LLM: Attempt 2
    LLM-->>Portkey: 500 Server Error
    Note over Portkey: Wait 2s backoff
    Portkey->>LLM: Attempt 3
    LLM-->>Portkey: 200 Success
    Portkey-->>App: Response delivered
"""

TIMEOUT_DIAGRAM = """
sequenceDiagram
    participant App
    participant Portkey
    participant LLM
    App->>Portkey: Request with 10s timeout
    Portkey->>LLM: Forward Request
    Note over LLM: Processing slowly...
    Note over Portkey: Timeout timer running
    Portkey-->>App: 408 Request Timeout
    Note over App: Retry or show error
"""

FALLBACK_DIAGRAM = """
graph LR
    A[Your App] -->|Request| B[Portkey Gateway]
    B -->|Try Primary| C[Large Model 70B]
    C -->|Fails with error| B
    B -->|Auto Fallback| D[Small Model 8B]
    D -->|Success| B
    B -->|Response| A
"""

RESILIENCE_DIAGRAM = """
sequenceDiagram
    participant App
    participant Portkey
    participant Primary as Primary Model
    participant Fallback as Fallback Model
    App->>Portkey: Request timeout=5s retry=2
    Portkey->>Primary: Attempt 1 of 2
    Note over Primary: Too slow or error...
    Portkey-->>Portkey: Timeout or 429 or 500
    Note over Portkey: Retry with backoff
    Portkey->>Primary: Attempt 2 of 2
    Primary-->>Portkey: Still failing
    Note over Portkey: All retries exhausted
    Note over Portkey: Activating fallback
    Portkey->>Fallback: Route to fallback model
    Fallback-->>Portkey: 200 Success
    Portkey-->>App: Response delivered
"""

LOAD_BALANCE_DIAGRAM = """
graph LR
    A[Your App] -->|10 Requests| B[Portkey Gateway]
    B -->|70 percent traffic| C[Large Model 70B]
    B -->|30 percent traffic| D[Small Model 8B]
    C -->|Responses| E[Results]
    D -->|Responses| E
    E -->|All responses| A
"""

CACHE_DIAGRAM = """
graph LR
    A[Your App] -->|Request| B[Portkey Gateway]
    B -->|Check Cache| C{Cache Hit?}
    C -->|YES instant| D[Return Cached Response]
    C -->|NO call LLM| E[Groq LLM]
    E -->|Store in Cache| F[Cache Store]
    F -->|Return Response| A
    D -->|Return Response| A
"""

RATE_LIMIT_DIAGRAM = """
sequenceDiagram
    participant App
    participant Portkey
    participant LLM
    App->>Portkey: Burst of requests
    Portkey->>LLM: Req 1 Success
    Portkey->>LLM: Req 2 Success
    Portkey->>LLM: Req 3 Success
    LLM-->>Portkey: 429 Too Many Requests
    Note over Portkey: Retry with backoff
    Portkey->>LLM: Retry request
    LLM-->>Portkey: Still 429
    Note over Portkey: Activate Fallback
    Portkey->>LLM: Switch to Fallback Model
    LLM-->>Portkey: 200 Success
    Portkey-->>App: Response delivered
"""

STREAMING_DIAGRAM = """
sequenceDiagram
    participant App
    participant Portkey
    participant LLM
    App->>Portkey: stream equals True
    Portkey->>LLM: Forward streaming request
    LLM-->>Portkey: token chunk 1
    Portkey-->>App: token chunk 1
    LLM-->>Portkey: token chunk 2
    Portkey-->>App: token chunk 2
    LLM-->>Portkey: more chunks
    Portkey-->>App: streamed live
    Note over Portkey: Full request logged in dashboard
"""

PRODUCTION_DIAGRAM = """
graph TD
    A[Your App] -->|Request| B[Portkey Gateway]
    B -->|Check| C{Cache Hit?}
    C -->|YES| D[Return Cached Response instantly]
    C -->|NO| E[Apply 30s Timeout]
    E -->|Try| F[Primary Model 70B]
    F -->|Success| G[Cache and Return]
    F -->|429 or 500| H[Retry up to 2 times]
    H -->|Still failing| I[Fallback to 8B Model]
    I -->|Success| G
    B -.->|All requests logged| J[Portkey Dashboard]
    G -->|Response| A
"""
