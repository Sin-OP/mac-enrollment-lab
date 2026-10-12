# GitLab source inventory — 2026-10-11

This is a read-only inventory of public GitLab projects located by the GitLab project index. It records source identity and provenance. A different file hash does not establish a different effective method, and a project's macOS version claim is not a hardware test result.

| GitLab project | Public source comparison | Assessment |
|---|---|---|
| [assafdori/bypass-mdm](https://gitlab.com/assafdori/bypass-mdm) | Both `bypass-mdm.sh` and `bypass-mdm-v2.sh` are byte-identical to the corresponding files in the [GitHub repository already listed in this project](https://github.com/assafdori/bypass-mdm). | This GitLab copy adds no distinct source for those two files. |
| [chrnbg/bmdm](https://gitlab.com/chrnbg/bmdm) | `bypass-mdm.sh` is byte-identical to Assaf Dori's file. Its `bypass-mdm-v2.sh` differs; line-sequence similarity to Assaf Dori's first script was about 0.71 and to the second about 0.11 at review time. | The variant needs separate evidence. Similarity is not proof of functional equivalence or effectiveness. |
| [maciej.klin/MDM](https://gitlab.com/maciej.klin/MDM) | Its `MDM-bypass.sh` differs from the compared Assaf Dori scripts; line-sequence similarity was about 0.11–0.13. | Distinct source, with no device or update-persistence evidence established by this inventory. |

The comparison used public `main` branch raw-file downloads on 2026-10-11. SHA-256 identities were checked across GitLab and GitHub for Assaf Dori's two scripts. No scripts from these projects were executed during this review. A close or distant text match cannot show how a script behaves on a particular Mac, whether enrollment is actually removed, or whether any result survives an update.

The project's [standalone support report](SYSTEM-REPORT.md) can collect OS, hardware, storage, and utility evidence without changing installation settings. Keep any actual device result tied to a precise macOS build, hardware model, script commit, and observed setup state. None of these source comparisons changes the project's current compatibility claims.
