               [ SERVER 1: VICIDIAL ]                              [ SERVER 2: STT SERVICE ]
     ┌────────────────────────────────────────┐          ┌────────────────────────────────────────┐
     │ OpenSUSE / ViciBox                     │          │ Python Service & Deepgram Pipelines    │
     │                                        │          │                                        │
     │  ┌──────────────────────────────────┐  │          │                                        │
     │  │ ViciDial / Asterisk 16 Core      │  │          │                                        │
     │  │  - Manages Calls                 │  │          │                                        │
     │  │  - Holds Lead/Campaign Metadata  │  │          │                                        │
     │  └────────────────┬─────────────────┘  │          │                                        │
     │                   │                    │          │                                        │
     │                   ▼                    │          │                                        │
     │  ┌──────────────────────────────────┐  │          │                                        │
     │  │ AMI Event Listener               │  │          │                                        │
     │  │  - Connects to localhost:5038    │  │          │                                        │
     │  │  - Listens for 'BridgeEnter'     │  │          │                                        │
     │  └────────────────┬─────────────────┘  │          │                                        │
     │                   │                    │          │                                        │
     │                   ▼                    │          │                                        │
     │  ┌──────────────────────────────────┐  │          │                                        │
     │  │ Metadata Fetcher                 │  │          │                                        │
     │  │  - Executes AMI 'GetVar'         │  │          │                                        │
     │  │  - Reads Lead ID, Vendor Code,   │  │          │                                        │
     │  │    Campaign & UniqueID           │  │          │                                        │
     │  └────────────────┬─────────────────┘  │          │                                        │
     │                   │                    │          │                                        │
     │                   ▼                    │          │                                        │
     │  ┌──────────────────────────────────┐  │          │                                        │
     │  │ External Media Trigger           │  │          │                                        │
     │  │  - Executes ARI HTTP Request to  │  │          │                                        │
     │  │    snoop Customer & Agent audio  │  │          │                                        │
     │  └────────────────┬─────────────────┘  │          │                                        │
     │                   │                    │          │                                        │
     │                   │ UDP RTP Streams    │          │  ┌──────────────────────────────────┐  │
     │                   └────────────────────┼──────────┼─>│ Dual UDP Listeners               │  │
     │                    - Customer: Port 20000         │  │  - Customer Stream (Port 20000)  │  │
     │                    - Agent: Port 20002 │          │  │  - Agent Stream (Port 20002)     │  │
     │                                        │          │  └────────────────┬─────────────────┘  │
     │                                        │          │                   │                    │
     │                                        │          │                   ▼                    │
     │                                        │          │  ┌──────────────────────────────────┐  │
     │                                        │          │  │ Audio Interleaver                │  │
     │                                        │          │  │  - Combines L/R into Stereo PCM  │  │
     │                                        │          │  └────────────────┬─────────────────┘  │
     │                                        │          │                   │                    │
     │                                        │          │                   ▼                    │
     │                                        │          │  ┌──────────────────────────────────┐  │
     │                                        │          │  │ Deepgram Nova-2 Engine           │  │
     │                                        │          │  │  - Multi-channel WebSocket       │  │
     │                                        │          │  │  - Isolated Speaker Transcripts  │  │
     │                                        │          │  └────────────────┬─────────────────┘  │
     │                                        │          │                   │                    │
     │                                        │          │                   ▼                    │
     │                                        │          │  ┌──────────────────────────────────┐  │
     │                                        │          │  │ Payload Builder & Webhook Sender │  │
     │                                        │          │  │  - Pairs Metadata + Transcripts  │  │
     │                                        │          │  │  - POSTs JSON Payload to CRM     │  │
     │                                        │          │  └────────────────┬─────────────────┘  │
     └────────────────────────────────────────┘          └───────────────────┼────────────────────┘
                                                                             │
                                                                             ▼
                                                                  [ YOUR CRM / DASHBOARD ]