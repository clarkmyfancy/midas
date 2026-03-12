# Midas iOS

SwiftUI starter for the Midas mobile client.

## Notes

- `project.yml` defines the XcodeGen project structure.
- `Midas/` contains the SwiftUI app entrypoint and starter views.
- `Midas/WithProGate.swift` provides the locked-state overlay used when a Pro capability is unavailable.
- HealthKit, App Intents, SSE streaming, and local privacy proxy logic can be added incrementally from this base.

## Getting Started

```bash
xcodegen generate
open Midas.xcodeproj
```

## Headless Build Check

```bash
xcodebuild -project Midas.xcodeproj -scheme Midas -sdk iphonesimulator -derivedDataPath .derived-data CODE_SIGNING_ALLOWED=NO build
```

This command was used to verify the current app sources compile in a simulator build.

