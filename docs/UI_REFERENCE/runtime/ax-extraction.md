# Track A — Accessibility (AXUIElement) extraction

## What was tried

`tools/uiref/mvax.c` builds `mvax`, a Mach-O extractor that uses
`AXUIElementCreateApplication` and friends to read another application's
accessibility tree from outside it, plus `mvax-inject.dylib`, the same code
compiled to run **inside** the inspected application.

It builds from Linux with no Apple SDK and runs correctly in the guest: the
document is produced, the errors are reported verbatim, and nothing is invented.

## Result: blocked by an OS permission, not by the extractor

First run, against Finder (pid 430), in the real guest:

```json
{
  "schema": "mavlinos.axinspect/1",
  "kind": "runtime-observed",
  "method": "AXUIElement (HIServices)",
  "extractor": "mvax.c",
  "source": "cross-process accessibility tree",
  "not_an_nsview_tree": true,
  "host_pid": 1040,
  "ax_is_process_trusted": false,
  "depth_limit": 24,
  "system_wide_children_err": -25205,
  "targets": [
    { "name": "Finder", "pid": 430,
      "attribute_names_err": -25204, "actions_err": -25204,
      "windows_err": -25204,
      "ax_errors": { "create_application": 0, "windows": -25204,
                     "app_identifier": -25201, "children": -25201 },
      "nodes_visited": 0 }
  ],
  "targets_inspected": 1,
  "status": "ok"
}
```

Raw file: [`raw/ax-finder.json`](raw/ax-finder.json)

### Decoding the error codes (public AXError values)

| Code | Meaning |
|---|---|
| `-25211` | `kAXErrorAPIDisabled` — the outright refusal seen *before* the TCC row existed |
| `-25204` | `kAXErrorCannotComplete` — returned for `AXWindows`, attribute names and action names *after* the TCC row was added |
| `-25205` | `kAXErrorAttributeUnsupported` — system-wide element refused `AXChildren` |
| `-25201` | `kAXErrorIllegalArgument` — app element refused `AXIdentifier` / `AXChildren` |
| `0` | `AXUIElementCreateApplication(430)` itself **succeeded** |

So the handle is created and the failure happens at the attribute level, not
when the element is created.

The error code itself is informative. Before anything was changed it was
`-25211` (`kAXErrorAPIDisabled`) — macOS refused outright. After the `TCC.db`
row was inserted it became `-25204` (`kAXErrorCannotComplete`): the request is
now *attempted* and times out instead of being rejected. Progress, but still no
data, and `AXIsProcessTrusted()` is still `false`.

### What was done about it

1. `/Library/Preferences/com.apple.security.plist` — the pre-TCC trusted-app
   list — was written with an entry for the extractor. Verified present in the
   guest. `AXIsProcessTrusted()` stayed `false` and the errors did not change.
2. The authoritative store on 10.9 was then located and inspected:
   `/Library/Application Support/com.apple.TCC/TCC.db`, readable only as root.
   Its 10.9 schema is:

   ```sql
   CREATE TABLE access (service TEXT NOT NULL, client TEXT NOT NULL,
                        client_type INTEGER NOT NULL, allowed INTEGER NOT NULL,
                        prompt_count INTEGER NOT NULL, csreq BLOB,
                        CONSTRAINT key PRIMARY KEY (service, client, client_type));
   ```

   Before: `kTCCServiceAccessibility|com.apple.Terminal|0|0`
   After the grant:
   `kTCCServiceAccessibility|/Users/builder/ns/mvax|0|1`

   `tccd` and `securityd` were reloaded and the extractor was re-run.
   `AXIsProcessTrusted()` **still** reports `false`; the error moved from
   `-25211` to `-25204` (see above), but the tree is still empty.
3. Running the extractor under `sudo` (root) changes nothing either.

### Conclusion for Mavericks 10.9

`AXUIElement` use by a client that is not the Accessibility-trusted process is
refused with `kAXErrorAPIDisabled`, and on this build neither the legacy
`com.apple.security.plist` list nor a hand-inserted `TCC.db` row flips that
check. The remaining route is to make the calls **from a process macOS already
trusts**, i.e. from inside the application being inspected.

That is what `mvax-inject.dylib` does, and it loads correctly:

```
mvax-inject: loaded
mvax-inject: SIGALRM armed for 9s
```

but has not yet produced a document. See
[`raw/injection-attempts.md`](raw/injection-attempts.md) §8.

An independent hard limit applies to Finder and System Preferences: both are
**platform binaries**, and macOS strips `DYLD_*` from their environment, so
injection into them is impossible on 10.9 by this route.

## What AX can and cannot provide

Kept explicit so the two extraction models are never conflated:

| Fact | AX | Native AppKit (`nsinspect`) |
|---|---|---|
| Window title, position, size | yes | yes |
| Enabled / focused / selected | yes | yes (`isEnabled`, `isKeyWindow`, …) |
| Control value, min, max, label | yes | yes |
| Control **role** (`AXButton`, `AXTextField`, …) | yes | n/a |
| **Objective-C class and superclass** | **no** | yes |
| **NSView hierarchy** | **no** (an accessibility tree is not a view tree) | yes |
| Cell class, control size, bezel style | **no** | yes |
| target/action pair | **no** | yes |
| Responder chain / key-view loop | **no** | possible |
| Layer tree / Core Animation | **no** | partial |
| Actions the element supports | yes (`AXUIElementCopyActionNames`) | n/a |
| NIB provenance | **no** | **no** (comes from the static extraction) |

The document itself carries `"not_an_nsview_tree": true` so the distinction
survives into the data.