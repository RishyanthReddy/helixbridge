# Verification

13 November 2026. No experimental binding validation is claimed.

- Python3.12.14: all35 existing unit tests passed, zero skipped.
- Offline demo: actual subprocess, validated metric artifact and checked resume passed.
- Python source compilation passed.
- All seven current target intervals/isoforms/endpoints were freshly checked against UniProt using the13 November manifest.
- Credential-value scan against both locally configured Modal tokens found zero matches in the export.
- Pinned public checkpoint preparation completed on a Modal CPU worker.
- First Modal GPU generation failed before inference because current AtomWorks removed an API required by the pinned RFD4 source. A mistaken second launch was cancelled; no successful result was claimed. Image now pins AtomWorks3.0.4 and Biotite1.6.0 from the historical working freeze and checks the generator import at build time. Qualification later passed.
- The build-time import check then caught missing Open Babel system libraries (libXrender). Added explicit system packages; this check avoids spending GPU time on import failures.
- A queued L40S-only request was stopped without a running container. GPU preference now allows L40S, A10G and A100.
- Real Modal generation passed: one60-aa seed43 candidate, exact target/binder identity checks,58.07s model-stage time and2564MiB reported reserved VRAM.
- Real independent Boltz-2 prediction and raw directional ipSAE passed on NVIDIA A10G:68.24s worker time. Exact chain identities, finite PAE, confidence and artifact hashes were checked by the existing adapter.
- Example summary and both model structures are in `../examples/verified-modal-run/`. Full archives remain in ignored local results and the account Volume. No ESMFold2 Modal qualification or updated-target candidate evaluation is claimed.
- A fresh Git clone independently passed the same35 tests and the real offline example.
- Original CIF fixture bytes are preserved; `.gitattributes` exempts their original spacing from whitespace checks.
