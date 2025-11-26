# Workflow Graph (Placeholder)
# Workflow Graphs - Project ORBIT

## 🔄 Complete System Workflow

```mermaid
flowchart TD
    Start([User Requests Dashboard]) --> CheckGCS{Dashboard<br/>exists in GCS?}
    
    CheckGCS -->|Yes| FetchGCS[Fetch from GCS]
    CheckGCS -->|No| Error[Return Error:<br/>Dashboard not found]
    
    FetchGCS --> Restructure{Restructure<br/>with GPT?}
    
    Restructure -->|Yes| GPTCleanup[GPT-4o<br/>Format Cleanup]
    Restructure -->|No| ReturnDirect[Return Dashboard]
    
    GPTCleanup --> ReturnDirect
    ReturnDirect --> End([Display to User])
    
    Error --> Suggest[Suggest: Run<br/>Supervisor Agent]
    Suggest --> End
    
    style Start fill:#e1f5e1
    style End fill:#e1f5e1
    style CheckGCS fill:#fff4e6
    style FetchGCS fill:#e3f2fd
    style GPTCleanup fill:#f3e5f5
    style Error fill:#ffebee
```

---

## 🤖 Supervisor Agent Workflow (ReAct)

```mermaid
flowchart TD
    Start([Agent Initialized]) --> Plan[Planner Node:<br/>Analyze Task]
    
    Plan --> FetchStructured[Action 1:<br/>Fetch Structured Payload]
    FetchStructured --> ObsStruct{Payload<br/>Found?}
    
    ObsStruct -->|Yes| ParseStruct[Parse Structured Data:<br/>Funding, Leadership, Metrics]
    ObsStruct -->|No| UseRAGOnly[Flag: Use RAG Only]
    
    ParseStruct --> FetchRAG[Action 2:<br/>Retrieve RAG Context]
    UseRAGOnly --> FetchRAG
    
    FetchRAG --> ObsRAG{Chunks<br/>Retrieved?}
    
    ObsRAG -->|Yes| MergeData[Data Merge Node:<br/>Combine Structured + RAG]
    ObsRAG -->|No| StructOnly[Use Structured Only]
    
    MergeData --> RiskCheck[Risk Detection Node:<br/>Search for Signals]
    StructOnly --> RiskCheck
    
    RiskCheck --> RiskFound{Risk<br/>Detected?}
    
    RiskFound -->|Yes| LogRisk[Action 3:<br/>report_risk]
    RiskFound -->|No| GenerateDash[Generation Node]
    
    LogRisk --> HITLCheck{Severity:<br/>High/Critical?}
    
    HITLCheck -->|Yes| HITL[HITL Node:<br/>Flag for Human Review]
    HITLCheck -->|No| GenerateDash
    
    HITL --> GenerateDash
    
    GenerateDash --> GPTSynth[GPT-4o Synthesis:<br/>Create 8-Section Dashboard]
    
    GPTSynth --> SaveGCS[Save to GCS:<br/>data/dashboards/company/]
    
    SaveGCS --> End([Dashboard Complete])
    
    style Start fill:#e1f5e1
    style End fill:#e1f5e1
    style Plan fill:#fff4e6
    style RiskCheck fill:#ffebee
    style HITL fill:#ff6b6b,color:#fff
    style GPTSynth fill:#f3e5f5
    style SaveGCS fill:#e3f2fd
```

---

## 🔄 Airflow ETL Pipeline Workflow

```mermaid
flowchart TD
    Trigger([Airflow Scheduler]) --> InitLoad{DAG Type}
    
    InitLoad -->|Initial Load| PrepFolder[Task: prep_company_folder<br/>Create directory structure]
    InitLoad -->|Daily Update| CheckUpdates[Task: check_for_updates<br/>Compare timestamps]
    InitLoad -->|Weekly Refresh| FullRefresh[Task: iterate_all_companies<br/>Loop through AI50 list]
    
    PrepFolder --> Scrape
    CheckUpdates --> Scrape
    FullRefresh --> Scrape
    
    Scrape[Task: scrape_company_data<br/>Multi-source web scraping]
    
    Scrape --> Sources{Scrape<br/>Sources}
    
    Sources -->|Homepage| ScrapeHome[Scrape Homepage]
    Sources -->|About| ScrapeAbout[Scrape About Page]
    Sources -->|Careers| ScrapeCareers[Scrape Careers]
    Sources -->|Blog| ScrapeBlog[Scrape Blog/News]
    Sources -->|RSS| ScrapeRSS[Parse RSS Feeds]
    
    ScrapeHome --> Extract
    ScrapeAbout --> Extract
    ScrapeCareers --> Extract
    ScrapeBlog --> Extract
    ScrapeRSS --> Extract
    
    Extract[Task: extract_structured_data<br/>Parse HTML → Pydantic Models]
    
    Extract --> Validate{Validation<br/>Passed?}
    
    Validate -->|Yes| SavePayload[Save to data/payloads/<br/>company.json]
    Validate -->|No| LogError[Log Validation Errors]
    
    SavePayload --> Chunk[Task: chunk_and_embed<br/>Text Splitting]
    
    Chunk --> Split[LangChain Splitter:<br/>500-1000 char chunks]
    
    Split --> Embed[OpenAI Embedding:<br/>text-embedding-3-small]
    
    Embed --> StoreVectors[Store in ChromaDB:<br/>Company collection]
    
    StoreVectors --> CallAgent[Task: generate_dashboard<br/>Call Supervisor Agent]
    
    CallAgent --> AgentRun[Supervisor executes ReAct loop]
    
    AgentRun --> DashGen[Generate unified dashboard]
    
    DashGen --> SaveDash[Save to GCS:<br/>gs://bucket/dashboards/]
    
    SaveDash --> Success([Pipeline Complete])
    
    LogError --> Retry{Retry<br/>Count < 3?}
    Retry -->|Yes| Extract
    Retry -->|No| Failed([Pipeline Failed])
    
    style Trigger fill:#e1f5e1
    style Success fill:#e1f5e1
    style Failed fill:#ffebee
    style CallAgent fill:#fff4e6
    style StoreVectors fill:#e3f2fd
    style SaveDash fill:#e3f2fd
```

---

## 📊 Dashboard Generation Workflow (Detailed)

```mermaid
flowchart TD
    Request([API Request]) --> MCPServer[MCP Server Receives]
    
    MCPServer --> CheckCache{Check<br/>Cache?}
    
    CheckCache -->|Enabled| CacheHit{Cache<br/>Hit?}
    CheckCache -->|Disabled| FetchGCS
    
    CacheHit -->|Yes| ReturnCache[Return Cached<br/>Dashboard]
    CacheHit -->|No| FetchGCS
    
    FetchGCS[Fetch from GCS:<br/>get_latest_dashboard]
    
    FetchGCS --> GCSFound{Dashboard<br/>Found?}
    
    GCSFound -->|Yes| LoadMD[Load .md file<br/>Filter out metadata.json]
    GCSFound -->|No| ReturnError[Return 404:<br/>Not Found Error]
    
    LoadMD --> ParseMeta[Parse Metadata:<br/>Extract data_sources]
    
    ParseMeta --> RestructureOpt{restructure_with_gpt<br/>= true?}
    
    RestructureOpt -->|Yes| CallGPT[Call GPT-4o:<br/>Clean & Format]
    RestructureOpt -->|No| Return
    
    CallGPT --> GPTProcess[GPT Processing:<br/>• Remove duplicates<br/>• Fix formatting<br/>• Improve structure]
    
    GPTProcess --> AddMeta[Add Metadata Footer:<br/>Tokens used, timestamp]
    
    AddMeta --> Return[Return Dashboard]
    
    Return --> UpdateCache{Cache<br/>Enabled?}
    
    UpdateCache -->|Yes| SetCache[Set Cache<br/>TTL: 1 hour]
    UpdateCache -->|No| Response
    
    SetCache --> Response[HTTP 200 Response]
    ReturnCache --> Response
    ReturnError --> Response
    
    Response --> End([Client Receives])
    
    style Request fill:#e1f5e1
    style End fill:#e1f5e1
    style FetchGCS fill:#e3f2fd
    style CallGPT fill:#f3e5f5
    style ReturnError fill:#ffebee
```

---

## 🎯 Risk Detection & HITL Workflow

```mermaid
flowchart TD
    Start([Risk Search Triggered]) --> RAGQuery[RAG Search:<br/>Query for risk keywords]
    
    RAGQuery --> Keywords{Search<br/>Terms}
    
    Keywords -->|Layoffs| SearchLayoff[Search: "layoff OR<br/>workforce reduction"]
    Keywords -->|Security| SearchSec[Search: "breach OR<br/>security incident"]
    Keywords -->|Legal| SearchLegal[Search: "lawsuit OR<br/>legal action"]
    Keywords -->|Financial| SearchFin[Search: "bankruptcy OR<br/>financial distress"]
    
    SearchLayoff --> Aggregate
    SearchSec --> Aggregate
    SearchLegal --> Aggregate
    SearchFin --> Aggregate
    
    Aggregate[Aggregate Results] --> ResultsFound{Risks<br/>Found?}
    
    ResultsFound -->|No| NoRisk[Log: No risks detected]
    ResultsFound -->|Yes| ParseRisk[Parse Risk Details:<br/>• Date<br/>• Description<br/>• Source URL]
    
    ParseRisk --> CreateSignal[Create RiskSignal Object]
    
    CreateSignal --> DetermineSeverity{Determine<br/>Severity}
    
    DetermineSeverity -->|Layoff > 20%| High
    DetermineSeverity -->|Security breach| Critical
    DetermineSeverity -->|Lawsuit| Medium
    DetermineSeverity -->|Other| Low
    
    High[Severity: High] --> LogRisk
    Critical[Severity: Critical] --> LogRisk
    Medium[Severity: Medium] --> LogRisk
    Low[Severity: Low] --> LogRisk
    
    LogRisk[Call: report_risk API]
    
    LogRisk --> SaveGCS[Save to GCS:<br/>data/risks/company/]
    
    SaveGCS --> HITLCheck{Severity:<br/>High or Critical?}
    
    HITLCheck -->|Yes| HITLFlag[Set HITL Flag:<br/>hitl_required = true]
    HITLCheck -->|No| AutoApprove[Auto-approve]
    
    HITLFlag --> Notify[Send Notification:<br/>Email/Slack alert]
    
    Notify --> HumanReview[Human Reviews Risk:<br/>Approve/Reject/Modify]
    
    HumanReview --> Decision{Human<br/>Decision}
    
    Decision -->|Approve| Include[Include in Dashboard]
    Decision -->|Reject| Exclude[Exclude from Dashboard]
    Decision -->|Modify| Update[Update Risk Details]
    
    Update --> Include
    
    AutoApprove --> Include
    NoRisk --> Continue
    
    Include --> Continue[Continue Pipeline]
    Exclude --> Continue
    
    Continue --> End([Risk Check Complete])
    
    style Start fill:#e1f5e1
    style End fill:#e1f5e1
    style HITLFlag fill:#ff6b6b,color:#fff
    style HumanReview fill:#ffd93d
    style Critical fill:#ff6b6b,color:#fff
    style High fill:#ff9800,color:#fff
```

---

## 🔁 Batch Processing Workflow

```mermaid
flowchart TD
    Start([Run: supervisor_mcp.py --all]) --> LoadCompanies[Load Forbes AI50 List:<br/>47 companies]
    
    LoadCompanies --> Confirm{User<br/>Confirms?}
    
    Confirm -->|No| Cancel([Cancelled])
    Confirm -->|Yes| InitAgent[Initialize Supervisor Agent]
    
    InitAgent --> StartLoop[Start Company Loop]
    
    StartLoop --> NextCompany{More<br/>Companies?}
    
    NextCompany -->|No| Summary
    NextCompany -->|Yes| Process[Process Company i/47]
    
    Process --> FetchStruct[Fetch Structured Data]
    
    FetchStruct --> StructFound{Data<br/>Found?}
    
    StructFound -->|Yes| GetRAG[Fetch RAG Context]
    StructFound -->|No| LogSkip[Log: Skipped - No data]
    
    GetRAG --> Merge[Merge Data Sources]
    
    Merge --> CallGPT[GPT-4o: Generate Dashboard]
    
    CallGPT --> SaveResult[Save to GCS]
    
    SaveResult --> LogSuccess[Log: Success ✓]
    
    LogSuccess --> RateLimit[Sleep 1 second<br/>Rate limiting]
    
    LogSkip --> RateLimit
    
    RateLimit --> NextCompany
    
    Summary[Generate Summary Report]
    
    Summary --> Stats[Calculate Stats:<br/>• Success count<br/>• Failed count<br/>• Total time]
    
    Stats --> SaveSummary[Save batch_results.json]
    
    SaveSummary --> End([Batch Complete])
    
    style Start fill:#e1f5e1
    style End fill:#e1f5e1
    style CallGPT fill:#f3e5f5
    style SaveResult fill:#e3f2fd
    style LogSuccess fill:#c8e6c9
```

---

## 🏭 Airflow DAG Execution Flow

```mermaid
flowchart TD
    Scheduler([Airflow Scheduler]) --> CheckSchedule{Schedule<br/>Triggered?}
    
    CheckSchedule -->|Daily 4AM| DailyDAG[orbit_daily_update_dag]
    CheckSchedule -->|Weekly Sun| WeeklyDAG[ai50_full_ingest_dag]
    CheckSchedule -->|Manual| InitialDAG[orbit_initial_load_dag]
    
    DailyDAG --> T1[Task: prep_company_folder]
    WeeklyDAG --> T1
    InitialDAG --> T1
    
    T1 --> T2[Task: scrape_company_data<br/>Parallel execution]
    
    T2 --> Parallel{Parallel<br/>Tasks}
    
    Parallel -->|Thread 1| Scrape1[Scrape: Homepage]
    Parallel -->|Thread 2| Scrape2[Scrape: About]
    Parallel -->|Thread 3| Scrape3[Scrape: Careers]
    Parallel -->|Thread 4| Scrape4[Scrape: Blog/News]
    
    Scrape1 --> Join[Join Results]
    Scrape2 --> Join
    Scrape3 --> Join
    Scrape4 --> Join
    
    Join --> T3[Task: extract_structured_data<br/>Pydantic validation]
    
    T3 --> Valid{Valid<br/>Data?}
    
    Valid -->|Yes| T4[Task: chunk_and_embed]
    Valid -->|No| Retry{Retry<br/>< 3?}
    
    Retry -->|Yes| T2
    Retry -->|No| MarkFailed[Mark Task Failed]
    
    T4 --> T5[Task: store_in_chromadb<br/>Upsert vectors]
    
    T5 --> T6[Task: generate_dashboard<br/>Call MCP Server]
    
    T6 --> T7[Task: save_to_gcs<br/>Persist dashboard]
    
    T7 --> Success([DAG Success])
    MarkFailed --> Failed([DAG Failed])
    
    style Scheduler fill:#e1f5e1
    style Success fill:#c8e6c9
    style Failed fill:#ffebee
    style T6 fill:#fff4e6
```

---

## 🔍 RAG Search Workflow

```mermaid
flowchart TD
    Query([User Query:<br/>"funding history"]) --> Preprocess[Preprocess Query:<br/>Lowercase, trim]
    
    Preprocess --> Embed[Generate Query Embedding:<br/>OpenAI API]
    
    Embed --> Vector[Query Vector:<br/>[0.123, -0.456, ...]]
    
    Vector --> ChromaSearch[ChromaDB Similarity Search]
    
    ChromaSearch --> Filter{Apply<br/>Filters?}
    
    Filter -->|Company ID| FilterCompany[Filter: company_id = "abridge"]
    Filter -->|Source Type| FilterSource[Filter: source_type = "blog"]
    Filter -->|None| NoFilter[No filters]
    
    FilterCompany --> Search
    FilterSource --> Search
    NoFilter --> Search
    
    Search[Cosine Similarity Search:<br/>top_k = 5]
    
    Search --> Results[Ranked Results:<br/>By distance score]
    
    Results --> Threshold{Distance<br/>< 1.5?}
    
    Threshold -->|Yes| Include[Include in Results]
    Threshold -->|No| Exclude[Exclude - Too dissimilar]
    
    Include --> Format[Format Response:<br/>JSON with metadata]
    Exclude --> Format
    
    Format --> Return([Return to Client])
    
    style Query fill:#e1f5e1
    style Return fill:#e1f5e1
    style Embed fill:#f3e5f5
    style ChromaSearch fill:#e3f2fd
```

---

## 🎨 Dashboard Synthesis Workflow

```mermaid
flowchart TD
    Start([Dashboard Generation Request]) --> GatherData[Gather Data Sources]
    
    GatherData --> Sources{Available<br/>Sources}
    
    Sources -->|Structured| LoadPayload[Load Pydantic Payload]
    Sources -->|RAG| LoadChunks[Load ChromaDB Chunks]
    Sources -->|Both| LoadBoth[Load Both Sources]
    
    LoadPayload --> FormatStruct[Format Structured Context:<br/>• Funding events<br/>• Leadership<br/>• Products]
    
    LoadChunks --> FormatRAG[Format RAG Context:<br/>• Top 3 chunks per section<br/>• 500 char limit]
    
    LoadBoth --> FormatStruct
    LoadBoth --> FormatRAG
    
    FormatStruct --> BuildPrompt
    FormatRAG --> BuildPrompt
    
    BuildPrompt[Build GPT Prompt]
    
    BuildPrompt --> System[System Prompt:<br/>"You are a PE analyst..."]
    
    System --> User[User Prompt:<br/>Company context + data]
    
    User --> CallGPT[Call GPT-4o API]
    
    CallGPT --> Generate[Generate Dashboard:<br/>temperature=0.3<br/>max_tokens=4000]
    
    Generate --> Parse[Parse Response:<br/>Extract markdown]
    
    Parse --> Validate{8 Sections<br/>Present?}
    
    Validate -->|Yes| AddFooter[Add Metadata Footer:<br/>• Data sources<br/>• Timestamp<br/>• Token count]
    Validate -->|No| Regenerate{Retry<br/>< 2?}
    
    Regenerate -->|Yes| CallGPT
    Regenerate -->|No| PartialDash[Return Partial Dashboard]
    
    AddFooter --> Complete[Dashboard Complete]
    PartialDash --> Complete
    
    Complete --> End([Return Dashboard])
    
    style Start fill:#e1f5e1
    style End fill:#e1f5e1
    style CallGPT fill:#f3e5f5
    style Generate fill:#f3e5f5
```

---

## 🌐 Multi-Service Communication Flow

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit UI
    participant MCP as MCP Server
    participant GCS as Google Cloud Storage
    participant GPT as OpenAI GPT-4o
    participant AF as Airflow
    
    User->>UI: Request dashboard for "anthropic"
    UI->>MCP: POST /tool/generate_unified_dashboard
    
    MCP->>GCS: Check for existing dashboard
    
    alt Dashboard exists
        GCS-->>MCP: Return unified_20251120.md
        
        opt Restructure enabled
            MCP->>GPT: Clean and format dashboard
            GPT-->>MCP: Improved markdown
        end
        
        MCP-->>UI: Return dashboard
        UI-->>User: Display dashboard
    
    else Dashboard not found
        MCP-->>UI: 404 - Not found
        UI-->>User: Show error + suggestion
        
        Note over User,AF: User runs supervisor agent manually
        
        User->>AF: Trigger orbit_initial_load_dag
        AF->>AF: Execute ETL pipeline
        AF->>MCP: Call /tool/generate_unified_dashboard
        MCP->>GPT: Generate new dashboard
        GPT-->>MCP: Return markdown
        MCP->>GCS: Save dashboard
        GCS-->>MCP: Confirm saved
        MCP-->>AF: Success
        AF-->>User: Pipeline complete
    end
```

---

## 🔐 Authentication & Authorization Flow

```mermaid
flowchart TD
    Request([Incoming Request]) --> CheckAuth{Auth<br/>Required?}
    
    CheckAuth -->|Airflow UI| AirflowAuth[Basic Auth:<br/>admin/admin]
    CheckAuth -->|MCP Server| NoAuth[No Auth<br/>Internal only]
    CheckAuth -->|GCS| GCSAuth[Service Account Auth]
    CheckAuth -->|ChromaDB| ChromaAuth[API Key Auth]
    CheckAuth -->|OpenAI| OpenAIAuth[API Key Auth]
    
    AirflowAuth --> ValidCreds{Valid<br/>Credentials?}
    
    ValidCreds -->|Yes| AllowAccess
    ValidCreds -->|No| Deny401[401 Unauthorized]
    
    GCSAuth --> CheckSA{Service Account<br/>Valid?}
    
    CheckSA -->|Yes| CheckPerms{Has Storage<br/>Permissions?}
    CheckSA -->|No| Deny403[403 Forbidden]
    
    CheckPerms -->|Yes| AllowAccess
    CheckPerms -->|No| Deny403
    
    ChromaAuth --> ValidKey{API Key<br/>Valid?}
    OpenAIAuth --> ValidKey
    
    ValidKey -->|Yes| AllowAccess
    ValidKey -->|No| Deny401
    
    NoAuth --> AllowAccess[Allow Access]
    
    AllowAccess --> ProcessRequest[Process Request]
    
    ProcessRequest --> End([Success])
    
    Deny401 --> End
    Deny403 --> End
    
    style Request fill:#e1f5e1
    style End fill:#e1f5e1
    style AllowAccess fill:#c8e6c9
    style Deny401 fill:#ffebee
    style Deny403 fill:#ffebee
```

---

## 📈 Scaling Architecture

```mermaid
flowchart TD
    LB[Load Balancer] --> Replicas{Scale<br/>Replicas}
    
    Replicas -->|Replica 1| MCP1[MCP Server 1<br/>Container]
    Replicas -->|Replica 2| MCP2[MCP Server 2<br/>Container]
    Replicas -->|Replica 3| MCP3[MCP Server 3<br/>Container]
    
    MCP1 --> Cache
    MCP2 --> Cache
    MCP3 --> Cache
    
    Cache[Redis Cache Layer<br/>Shared cache]
    
    Cache --> CacheHit{Cache<br/>Hit?}
    
    CacheHit -->|Yes| ReturnFast[Return Cached<br/>Response time: ~50ms]
    CacheHit -->|No| Backends
    
    Backends{Backend<br/>Services}
    
    Backends -->|Storage| GCS[Google Cloud Storage<br/>Multi-region]
    Backends -->|Vectors| Chroma[ChromaDB Cloud<br/>Managed service]
    Backends -->|LLM| OpenAI[OpenAI API<br/>Load balanced]
    
    GCS --> ReturnSlow
    Chroma --> ReturnSlow
    OpenAI --> ReturnSlow
    
    ReturnSlow[Return Fresh Data<br/>Response time: ~2-5s]
    
    ReturnSlow --> UpdateCache[Update Cache<br/>TTL: 1 hour]
    
    UpdateCache --> Response[Return to Client]
    ReturnFast --> Response
    
    Response --> End([Complete])
    
    style LB fill:#e1f5e1
    style End fill:#e1f5e1
    style Cache fill:#fff4e6
    style ReturnFast fill:#c8e6c9
```

---

## 🎯 Key Workflow Patterns

### Pattern 1: Fan-Out / Fan-In (Airflow)
```
Single DAG trigger → Multiple parallel scrape tasks → Join → Continue
```

### Pattern 2: Cache-Aside (MCP Server)
```
Check cache → If miss, fetch from GCS → Update cache → Return
```

### Pattern 3: Retry with Exponential Backoff
```
API call fails → Wait 1s → Retry → Wait 2s → Retry → Wait 4s → Give up
```

### Pattern 4: Circuit Breaker
```
If GCS fails 5 times → Open circuit → Return cached/error for 60s → Close circuit
```

### Pattern 5: Async Processing
```
User requests dashboard → Return 202 Accepted → Process in background → Notify when complete
```

---

## 📊 Performance Characteristics

| Workflow | Latency | Throughput | Bottleneck |
|----------|---------|------------|------------|
| Fetch from GCS | 200-500ms | 1000 req/s | Network I/O |
| RAG Search | 500-1000ms | 100 req/s | ChromaDB query |
| Dashboard Generation | 10-30s | 10 req/min | GPT-4o API |
| Airflow DAG | 5-15 min | 1 company/min | Web scraping |
| Batch Processing | 30-60 min | 47 companies/hr | Rate limits |

---

## 🎓 Workflow Best Practices

1. **Idempotency** - Re-running same workflow produces same result
2. **Atomicity** - Each task is atomic (all-or-nothing)
3. **Observability** - Every step is logged
4. **Fault Tolerance** - Graceful failures with retries
5. **Rate Limiting** - Respect API quotas
6. **Caching** - Reduce redundant operations
7. **Parallelization** - Use concurrency where possible
