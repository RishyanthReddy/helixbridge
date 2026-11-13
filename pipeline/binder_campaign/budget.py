"""Conservative admission for one-GPU Slurm jobs under a shared bounded budget."""
TERMINAL = {'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY',
            'PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}


def admission(ledger, observed, requested_seconds):
    if ledger.get('unresolved_submission'):
        raise ValueError('Unresolved submission intent; reconcile with Slurm first')
    if type(requested_seconds) is not int or requested_seconds <= 0:
        raise ValueError('A positive integer job limit is required')
    jobs=ledger['jobs']; ids=[row['job_id'] for row in jobs]
    if len(ids)!=len(set(ids)) or set(ids)!=set(observed):
        raise ValueError('Scheduler observations must cover each ledger job exactly once')
    used=reserved=active=0
    for row in jobs:
        observation=observed[row['job_id']]
        elapsed=observation['elapsed_seconds']
        if type(elapsed) is not int or elapsed<0:
            raise ValueError('Invalid scheduler elapsed time')
        state=observation['state'].split()[0].rstrip('+')
        used+=elapsed
        if state not in TERMINAL:
            active+=1
            remaining=observation.get('remaining_seconds',0)
            if type(remaining) is not int or remaining<0:
                raise ValueError('Invalid scheduler remaining time')
            reserved+=max(0,row['limit_seconds']-elapsed,remaining)
    if active>=ledger['max_concurrent_gpus']:
        raise ValueError('Concurrent GPU admission limit reached')
    if used+reserved+requested_seconds>ledger['gpu_seconds_cap']:
        raise ValueError('GPU budget cannot cover the requested hard time limit')
    return {'used_gpu_seconds':used,'reserved_gpu_seconds':reserved,
            'active_jobs':active,'remaining_unreserved_seconds':ledger['gpu_seconds_cap']-used-reserved}
