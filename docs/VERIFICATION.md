# Verification

13 November 2026. No experimental binding validation is claimed.

- Python3.12.14: all35 existing unit tests passed, zero skipped.
- Offline demo: actual subprocess, validated metric artifact and checked resume passed.
- Python source compilation passed.
- All seven current target intervals/isoforms/endpoints were freshly checked against UniProt using the13 November manifest.
- Credential-value scan against both locally configured Modal tokens found zero matches in the export.
- Pinned public checkpoint preparation completed on a Modal CPU worker.
- First Modal GPU generation failed before inference because current AtomWorks removed an API required by the pinned RFD4 source. A mistaken second launch was cancelled; no successful result was claimed. Image now pins AtomWorks3.0.4 and Biotite1.6.0 from the historical working freeze and checks the generator import at build time. Qualification retry is in progress.
- Modal generation and independent evaluation outcomes will be recorded below after completion.
- Original CIF fixture bytes are preserved; `.gitattributes` exempts their original spacing from whitespace checks.
