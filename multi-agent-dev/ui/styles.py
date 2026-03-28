"""CSS styles for the Streamlit UI."""

MAIN_CSS = """
<style>
    .block-container { max-width: 950px; }

    /* Phase divider */
    .phase-divider {
        display: flex;
        align-items: center;
        margin: 24px 0 12px 0;
        gap: 12px;
    }
    .phase-divider::before, .phase-divider::after {
        content: '';
        flex: 1;
        height: 1px;
        background: linear-gradient(to right, transparent, #bdbdbd, transparent);
    }
    .phase-divider-text {
        font-size: 0.9em;
        font-weight: 600;
        color: #546e7a;
        white-space: nowrap;
        letter-spacing: 2px;
    }

    /* Message header */
    .msg-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 2px;
    }
    .msg-speaker {
        font-weight: 700;
        font-size: 0.95em;
    }
    .msg-role-tag {
        font-size: 0.75em;
        padding: 1px 8px;
        border-radius: 10px;
        font-weight: 500;
    }
    .tag-pm { background: #e8f5e9; color: #2e7d32; }
    .tag-architect { background: #e3f2fd; color: #1565c0; }
    .tag-programmer { background: #fff3e0; color: #e65100; }
    .tag-reviewer { background: #fce4ec; color: #c62828; }
    .tag-system { background: #f3e5f5; color: #7b1fa2; }

    /* Tool call block */
    .tool-call {
        background: #f5f5f5;
        border-left: 3px solid #90a4ae;
        padding: 6px 12px;
        margin: 4px 0;
        font-size: 0.85em;
        font-family: monospace;
        border-radius: 0 4px 4px 0;
    }
    .tool-result {
        background: #fafafa;
        border-left: 3px solid #66bb6a;
        padding: 6px 12px;
        margin: 4px 0;
        font-size: 0.82em;
        font-family: monospace;
        border-radius: 0 4px 4px 0;
        max-height: 200px;
        overflow-y: auto;
    }

    /* File change indicator */
    .file-change {
        background: #e8f5e9;
        border-left: 3px solid #4caf50;
        padding: 4px 12px;
        margin: 4px 0;
        font-size: 0.85em;
    }
</style>
"""
