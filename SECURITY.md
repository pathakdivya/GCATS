# Security Policy

G-CATS is a desktop application for collecting continuous affect ratings in research settings. It runs locally, makes no network connections, and writes data only to the folders you choose. This policy explains how to report security problems and how to keep participant data safe while using the software.

## Supported Versions

Only the latest release receives security fixes. Please update before reporting a problem.

| Version | Supported |
| ------- | --------- |
| Latest release | Yes |
| Older releases | No |

## Reporting a Vulnerability

Please do **not** open a public GitHub issue for security problems.

Report privately through GitHub's **Report a vulnerability** button on the repository's Security tab, or email **divyap@iitk.ac.in** or **divyapat22@gmail.com** with the subject line `GCATS security`.

Please include:
- the GCATS version and your operating system
- a description of the problem and its possible impact
- steps to reproduce it, and any proof-of-concept files (for example a preset or stimulus file)

What to expect:
- an acknowledgement within 7 days
- an initial assessment within 14 days
- a fix or mitigation in the next release when the report is confirmed, with credit to you unless you prefer to stay anonymous

This is an academic project maintained by a small team, so response times are best-effort.

## Scope

In scope:
- the G-CATS source code in this repository and the official Windows installer
- handling of preset (JSON) files, stimulus files and output data files
- anything that could expose, corrupt or silently alter recorded participant data

Out of scope:
- vulnerabilities in third-party dependencies (PySide6, pygame, ffpyplayer); please report those upstream, though we welcome a note so we can update our pinned versions
- problems that need an attacker to already control the computer running G-CATS
- unofficial builds or modified copies

## Participant Data

GCATS records self-report data that may be sensitive. The software does not encrypt, upload or anonymise data on its own. Researchers are responsible for:
- using participant codes, not names or other identifying details, in the Participant fields
- storing output folders on encrypted, access-controlled drives in line with their ethics approval and data protection law (check with your Institute Ethics Board or applicable country law)
- removing identifying information before sharing data publicly
- only loading presets and stimulus files from trusted sources

## Verifying Downloads

Download the installer only from this repository's Releases page, Sourceforge.net link or the project's Zenodo record. Check the published SHA-256 checksum before installing.
