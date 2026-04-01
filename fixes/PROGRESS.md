# Fixes Progress

Started: 2026-03-09

## Phase 1: Configuration Chaos

- [x] Step 1: Audit complete
- [x] Step 2: Config manager created (in `core/config.py` to preserve imports)
- [x] Step 3: Initial file migrations done (`Main.py`, `core/auth.py`, env helpers, chatbot flags)

## Phase 2: Import Hell

- [x] Step 1: Import map generated
- [x] Step 2: Circular-import inventory generated
- [x] Step 3: `__init__.py` inventory generated

## Phase 3: Resource Leaks

- [x] Step 1: Resource audit files generated
- [x] Step 2: Camera cleanup reviewed (`core/auth.py` has try/finally release)
- [x] Step 3: Thread shutdown improvements (`realtime_conversation.py`, `stt.py`, `tts.py`)

## Phase 4: Error Handling

- [x] Step 1: Error handling inventory generated
- [x] Step 2: Exception hierarchy created (`core/exceptions.py`)
- [x] Step 3: `action_executor.py` exception migration + caller updates

## Phase 5: Security Gaps

- [x] Step 1: PIN hashing hardened (PBKDF2 + salt + legacy upgrade path)
- [x] Step 2: Command injection hardening in `core/Assistant.py`
- [~] Step 3: File write validation rolled out in chat panel/download paths (full repo-wide rollout pending)

## Phase 6: Race Conditions

- [x] Step 1: Lock utility created (`core/filelock.py`)
- [x] Step 2: `chat_panel.py` lock integration

## Phase 7: Memory Bloat

- [x] Step 1: Chat history cap in chatbot
- [x] Step 2: Cache cleanup utility created (`core/cache_cleaner.py`)
- [x] Step 3: Vector store pruning added (`core/vector_memory.py`)

## Phase 8: Input Validation

- [x] Step 1: Input audit generated
- [x] Step 2: Validation module created (`core/validation.py`)
- [x] Step 3: `safe_control.py` download hardening implemented

## Phase 9: Hardcoded Paths

- [x] Step 1: PathManager created (`core/paths.py`)
- [x] Step 2: Hardcoded path inventory generated

## Phase 10: Qt Memory Leaks

- [x] Step 1: Qt widget audit generated (`fixes/qt_widgets.txt`)
- [x] Step 2: `main_window.py` popup/web cleanup implemented
