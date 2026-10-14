// Compare every string an old bundle and a new bundle resolve to, per language.
//
// Build:  swiftc -o /tmp/compare_bundles <skill>/scripts/compare_bundles.swift
// Run:    /tmp/compare_bundles <old> <new.app> [Table]
//
// <old> is any directory holding <lang>.lproj/<Table>.strings (the snapshot
// taken before migration), or the old .app. Each key is formatted at counts 1
// and 5, with string arguments filled by markers, so plural and positional
// changes show up. Expected result after a pure migration: only the plural
// fixes you intended.
import Foundation

let args = CommandLine.arguments
guard args.count >= 3 else { print("usage: compare_bundles <old> <new.app> [Table]"); exit(2) }
let table = args.count > 3 ? args[3] : "Localizable"

func lprojDir(_ root: String, _ lang: String) -> String? {
    for p in ["\(root)/Contents/Resources/\(lang).lproj", "\(root)/\(lang).lproj"]
    where FileManager.default.fileExists(atPath: p) { return p }
    return nil
}
func languages(_ root: String) -> [String] {
    let dir = FileManager.default.fileExists(atPath: "\(root)/Contents/Resources") ? "\(root)/Contents/Resources" : root
    return ((try? FileManager.default.contentsOfDirectory(atPath: dir)) ?? [])
        .filter { $0.hasSuffix(".lproj") && $0 != "Base.lproj" }.map { String($0.dropLast(6)) }.sorted()
}
func arguments(_ fmt: String, _ n: Int) -> [CVarArg] {
    let re = try! NSRegularExpression(pattern: "%(\\d+\\$)?(#@\\w+@|l?l?[di]|@)")
    var slots: [Int: CVarArg] = [:], next = 1
    for m in re.matches(in: fmt, range: NSRange(fmt.startIndex..., in: fmt)) {
        let s = (fmt as NSString).substring(with: m.range)
        var idx = next
        if let r = Range(m.range(at: 1), in: fmt) { idx = Int(fmt[r].dropLast())! } else { next += 1 }
        slots[idx] = s.hasSuffix("@") && !s.contains("#") ? "«\(idx)»" as NSString : n
    }
    guard let top = slots.keys.max() else { return [] }
    return (1...top).map { slots[$0] ?? n }
}

let (oldRoot, newRoot) = (args[1], args[2])
var total = 0, diffs = 0
for lang in languages(oldRoot) {
    guard let od = lprojDir(oldRoot, lang), let o = Bundle(path: od) else { continue }
    guard let nd = lprojDir(newRoot, lang), let nb = Bundle(path: nd) else { print("[\(lang)] missing in new bundle"); diffs += 1; continue }
    let keys = (NSDictionary(contentsOfFile: "\(od)/\(table).strings") as? [String: Any])?.keys.sorted() ?? []
    for k in keys {
        let of = o.localizedString(forKey: k, value: "∅", table: table)
        let nf = nb.localizedString(forKey: k, value: "∅", table: table)
        for n in [1, 5] {
            total += 1
            let a = arguments(of, n)
            let loc = Locale(identifier: lang)
            let ov = a.isEmpty ? of : String(format: of, locale: loc, arguments: a)
            let nv = a.isEmpty ? nf : String(format: nf, locale: loc, arguments: a)
            if ov != nv { diffs += 1; print("[\(lang)] \(k) n=\(n)\n   old: \(ov)\n   new: \(nv)") }
        }
    }
}
print("\(total) checks, \(diffs) differ")
