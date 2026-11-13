# Third-party sources

No upstream model code or checkpoints are vendored. Install/download them from the original source; their code, weight and data licenses apply separately.

| Component | Pinned source / purpose |
|---|---|
| RFD4-Proteina | https://github.com/RosettaCommons/RFD4-Proteina/tree/ddd934f7e6b86f7582ce487d5b19f6c526c644b5 ; BSD-3-Clause source; native generation |
| RFD4 weights | https://huggingface.co/nvidia/RFD4-Proteina/tree/621b785abf9d61dd24f4b81ae4dbd1330728f030 ; release hashes checked by fetch script; consult model license |
| Boltz | https://github.com/jwohlwend/boltz ; Python package2.2.1; independent prediction |
| Boltz weights | https://huggingface.co/boltz-community/boltz-2/tree/6fdef46d763fee7fbb83ca5501ccceff43b85607 ; consult model license |
| ipSAE | https://github.com/DunbrackLab/IPSAE/tree/6174cf9e71cb1bd660cc805856a18c4871a6dec3 ; raw directional scores |
| UniProt | https://www.uniprot.org/ ; target sequences, source/checksum recording by target preparation |
| ColabFold | https://github.com/sokrypton/ColabFold ; public target-only MSA service; no candidate MSA request in the example |
| Competition | https://aiprotein.sjtu.edu.cn/targets and https://aiprotein.sjtu.edu.cn/rules |
| Modal | https://modal.com/docs/guide ; runtime and account-specific billing |

Historical public target/reference provenance and limitations are retained in the example audit and historical target manifest. This private team snapshot grants no blanket license over third-party materials. Recheck licenses before redistribution outside the team.
