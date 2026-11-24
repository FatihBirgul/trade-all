# V9 import, state and operational security

Retained lexical refusal covers POSIX/Windows traversal, UNC/rooted/drive-relative/
ADS paths, symlinks, unsupported formats and arbitrary API filesystem paths. Raw
read8MB, rows2000, JSON depth32, duplicate keys/nonfinite numerics/strict fields,
closed times and identity are bounded; no archive extraction/decompression added.

On supported POSIX: descriptor-relative O_DIRECTORY/O_NOFOLLOW traversal, root
inode/device binding, file identity/size/mtime/ctime comparison before/open/after
read and final path check. This reduces check/open and directory replacement races.
Windows lacks this descriptor boundary. Default fallback requires a trusted,
operator-owned import namespace; hostile concurrent directory mutation is not a
certified Windows guarantee. For that threat set require_descriptor_boundary=True;
unsupported platforms refuse rather than silently claiming equal isolation.

Actual Windows3.12 CI42243686985 exposed CPython stat/fstat ctime disagreement on
an unchanged file (https://github.com/python/cpython/issues/157671). f1cf856 omits
ctime only for cross-API Windows path/handle comparison; same-handle before/after
checks still include ctime. Device/inode/size/mtime remain checked everywhere.
Independent signature regression and all four new CI jobs passed; no skip hid it.

Optional local checkpoint store requires trusted configured project root; no
adversarial multi-user storage/digital-signature claim. Pilot JSON is untrusted
whitelisted local evidence; hashes never authenticate source/license/PIT truth.
Local preregistry/journal locks and bounds are process-local, not a distributed
transaction service. API retains localhost default, no wildcard CORS, no public
authentication implication, bounded work and generic errors. Existing no-order
SDK dispatch guard, scanner/provider/cache/cancellation regressions are preserved.
No order_send/order_check, auto-paper, production DB, protected-source write,
public deployment or credentials were introduced or executed.
