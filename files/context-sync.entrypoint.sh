#!/bin/bash
# The job my-setup.context-sync, for job-runner (separate project, ~/dev/job-runner): runs context-sync (files/context_sync.sh),
# which copies the Drive folder Personal/my-context/ to the read-only local copy every agent loads, commits its history and
# sends the copy to the VM. Deployed by modules/my_context.sh to ~/opt/my-setup/context-sync.sh; this Mac's trigger
# com.jeanlescut.my-setup.context-sync runs it every 15 min: that is the whole schedule.
# Requirements:
#   - the Mac only (the only machine with the Drive); the VM gets its copy from here
#   - every 15 min (StartInterval 900): an edit nobody synced (by hand, or by a web AI) reaches the agents within 15 min
#   - no "already done" rule: every trigger works
#   - timeout 10 min, shorter than the period: overlap impossible, no claim
#   - the Drive unreachable (exit 3): WAIT, the agents keep loading the last copy
#   - summary: the "history:" / "copied" / "WARN" line
. ~/opt/job-runner/lib.sh

jr_execute 10 "$HOME/opt/my-setup/context/context-sync"
[ "$JR_RC" = 3 ] && jr_write_status WAIT "the Drive folder is unreachable: agents load the last copy"
jr_summary_grep '^(history:|copied|WARN)'
