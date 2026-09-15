# EDF portable backup

This ZIP contains the separately sealed `edf555760245-0223f1d6bacc` Windows package. It preserves the exact EDF application source and bundled Python/native runtime identified in `edf-portable-archive-manifest.json`.

1. Verify the ZIP SHA256 against that manifest, then extract it into a new directory. Keep earlier 5e8 or 52bd packages separate.
2. The extracted folder contains `OMA.cmd`, `Start-OMA.ps1`, its bundled runtime, and `artifact-files.json`. Launch `OMA.cmd` when you intend to start that copy. Existing running services and their Store directories should be handled separately.
3. Application data is a separate backup. Use the existing verified Store backup and its RESTORE instructions; this package is not a replacement for those Store/source archives. Preserve the original backup and restore into a new location.

Original-native and custom-native suites each passed 3012 exact cases. The bundled run passed 3009 plus the three named direct-interpreter bridge cases marked not applicable; those three passed in the other environments. Three unchanged saved Office IFC exports were freshly rechecked. The source and evidence are limited to the declared supported numerical models, finite catalogues and native check scope; this is not a complete original-mathematics or unrestricted/global building optimization claim.

The next private compact-search module is absent. Six prebuilt UI assets are unchanged. The original 5e8 archive remains a distinct historical backup. This archive is prepared for the user's private GitHub backup; no public redistribution approval is asserted.
