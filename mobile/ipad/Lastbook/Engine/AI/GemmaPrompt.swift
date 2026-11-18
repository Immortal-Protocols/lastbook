import Foundation

/// Gemma 4's own prompt format and tool-call notation, ported from desktop llm_local.py (render, declaration, parse_calls,
/// size_of). The prompt is a list of segments: template markup (special tokens count) or plain text (they never do), so a
/// document holding "<|turn>" stays text and cannot start a turn of its own.
typealias Segment = (text: String, special: Bool)

enum GemmaPrompt {
    static let Q = "<|\"|>"

    /// format_argument from the model's chat template, for values the app writes (tool calls it saw and parsed).
    static func arg(_ v: Any?) -> [Segment] {
        guard let v, !(v is NSNull) else { return [("null", true)] }
        if let n = v as? NSNumber, CFGetTypeID(n) == CFBooleanGetTypeID() { return [(n.boolValue ? "true" : "false", true)] }
        if let b = v as? Bool { return [(b ? "true" : "false", true)] }
        if let s = v as? String { return [(Q, true), (s, false), (Q, true)] }
        if let n = v as? NSNumber { return [(pyNum(n), true)] }
        if let d = v as? [String: Any] {
            var out: [Segment] = [("{", true)]
            for (i, k) in d.keys.sorted(by: pyLT).enumerated() {
                if i > 0 { out.append((",", true)) }
                out.append((k + ":", true))
                out += arg(d[k])
            }
            return out + [("}", true)]
        }
        if let a = v as? [Any] {
            var out: [Segment] = [("[", true)]
            for (i, x) in a.enumerated() {
                if i > 0 { out.append((",", true)) }
                out += arg(x)
            }
            return out + [("]", true)]
        }
        return [("\(v)", false)]
    }

    static func pyNum(_ n: NSNumber) -> String {
        let d = n.doubleValue
        if d == d.rounded(), abs(d) < 1e15, !String(describing: n).contains(".") { return String(n.int64Value) }
        return String(d)
    }

    static func params(_ props: [String: Any]) -> String {
        var out: [String] = []
        for (i, key) in props.keys.sorted(by: pyLT).enumerated() {
            let v = props[key] as? [String: Any] ?? [:]
            let s = (i > 0 ? "," : "") + key + ":{"
            var parts: [String] = []
            if let d = v["description"] as? String, !d.isEmpty { parts.append("description:\(Q)\(d)\(Q)") }
            let t = ((v["type"] as? String) ?? "").uppercased()
            if t == "STRING", let e = v["enum"] as? [String], !e.isEmpty {
                parts.append("enum:[" + e.map { "\(Q)\($0)\(Q)" }.joined(separator: ",") + "]")
            } else if t == "ARRAY", let items = v["items"] as? [String: Any], !items.isEmpty {
                var its: [String] = []
                for ik in items.keys.sorted(by: pyLT) {
                    guard let iv = items[ik], !(iv is NSNull) else { continue }
                    its.append(ik == "type" ? "type:\(Q)\("\(iv)".uppercased())\(Q)" : "\(ik):\(iv)")
                }
                parts.append("items:{" + its.joined(separator: ",") + "}")
            }
            parts.append("type:\(Q)\(t)\(Q)")
            out.append(s + parts.joined(separator: ",") + "}")
        }
        return out.joined()
    }

    static func declaration(_ tool: Rec) -> String {
        let f = tool["function"] as? Rec ?? [:]
        let p = f["parameters"] as? Rec ?? [:]
        var s = "declaration:\(f.s("name")){description:\(Q)\(f.s("description"))\(Q)"
        if !p.isEmpty {
            s += ",parameters:{"
            if let props = p["properties"] as? Rec, !props.isEmpty { s += "properties:{" + params(props) + "}," }
            if let req = p["required"] as? [String], !req.isEmpty { s += "required:[" + req.map { "\(Q)\($0)\(Q)" }.joined(separator: ",") + "]," }
            if let t = p["type"] as? String, !t.isEmpty { s += "type:\(Q)\(t.uppercased())\(Q)}" }
        }
        return s + "}"
    }

    static func text(_ m: Rec) -> String {
        if let c = m["content"] as? String { return c }
        if let parts = m["content"] as? [Rec] {
            return parts.filter { $0.s("type") == "text" }.map { $0.s("text") }.joined(separator: " ")
        }
        return ""
    }

    static func stripThinking(_ t: String) -> String {
        pyStrip(Rx.sub(#"(?s)<\|channel>.*?<channel\|>"#, "", t))
    }

    /// OpenAI-shaped messages to Gemma 4 segments, as the model's chat template lays them out, with thinking off. System
    /// messages before the model's first reply in this turn go together at the top: instructions, sources, then the question.
    static func render(_ msgs: [Rec], tools: [Rec]?) -> [Segment] {
        let lastUser = msgs.indices.last(where: { msgs[$0].s("role") == "user" }) ?? -1
        let firstReply = msgs.indices.first(where: { $0 > lastUser && ["assistant", "tool"].contains(msgs[$0].s("role")) }) ?? msgs.count
        let top = msgs.enumerated().filter { $0.element.s("role") == "system" && $0.offset < firstReply }.map { $0.element }
        let rest = msgs.enumerated().filter { !($0.element.s("role") == "system" && $0.offset < firstReply) }.map { $0.element }
        var seg: [Segment] = [("<|turn>system\n", true)]
        seg.append((top.map { pyStrip(text($0)) }.joined(separator: "\n\n"), false))
        for t in tools ?? [] { seg += [("<|tool>", true), (declaration(t), true), ("<tool|>", true)] }
        seg.append(("<turn|>\n", true))
        var i = 0
        var openModel = false
        while i < rest.count {
            let m = rest[i]
            let role = m.s("role")
            if role == "assistant" {
                if !openModel { seg.append(("<|turn>model\n", true)) }
                let calls = m["tool_calls"] as? [Rec] ?? []
                for c in calls {
                    let f = c["function"] as? Rec ?? [:]
                    var args: Rec = [:]
                    if let s = f["arguments"] as? String {
                        args = (try? JSONSerialization.jsonObject(with: Data((s.isEmpty ? "{}" : s).utf8))) as? Rec ?? [:]
                    } else if let d = f["arguments"] as? Rec { args = d }
                    seg.append(("<|tool_call>call:" + f.s("name") + "{", true))
                    for (j, k) in args.keys.sorted(by: pyLT).enumerated() {
                        if j > 0 { seg.append((",", true)) }
                        seg.append((k + ":", true))
                        seg += arg(args[k])
                    }
                    seg.append(("}<tool_call|>", true))
                }
                var names: [String: String] = [:]
                for c in calls { names[c.s("id")] = (c["function"] as? Rec)?.s("name") ?? "unknown" }
                var j = i + 1
                var hadTools = false
                while j < rest.count, rest[j].s("role") == "tool" {
                    let t = rest[j]
                    let name = names[t.s("tool_call_id")] ?? "unknown"
                    seg += [("<|tool_response>response:" + name + "{value:" + Q, true), (text(t), false), (Q + "}<tool_response|>", true)]
                    hadTools = true
                    j += 1
                }
                let content = pyTruthy(m["content"]) ? stripThinking(text(m)) : ""
                if !content.isEmpty { seg.append((content, false)) }
                let nxt: String? = j < rest.count ? rest[j].s("role") : nil
                if hadTools && content.isEmpty && nxt == nil {
                    openModel = true
                } else if nxt == "assistant" && (calls.isEmpty || hadTools) {
                    openModel = true
                } else {
                    seg.append(("<turn|>\n", true))
                    openModel = false
                }
                i = j
                continue
            }
            if role == "tool" {
                seg += [("<|turn>user\n", true), (pyStrip(text(m)), false), ("<turn|>\n", true)]
            } else {
                seg += [("<|turn>" + role + "\n", true), (pyStrip(text(m)), false), ("<turn|>\n", true)]
            }
            openModel = false
            i += 1
        }
        if !openModel { seg.append(("<|turn>model\n<|channel>thought\n<channel|>", true)) }
        return seg
    }

    /// A rough count of tokens, on the high side: about 3.2 characters a token for English text (desktop size_of).
    static func sizeOf(_ segs: [Segment]) -> Double {
        Double(segs.reduce(0) { $0 + $1.text.unicodeScalars.count }) / 3.2 + 8 * Double(segs.count)
    }

    // ------------------------------------------------------------------------------------------- Gemma's tool calls --
    static let CALL = #"(?s)<\|tool_call>call:([A-Za-z_][\w.-]*)\{(.*?)\}<tool_call\|>"#

    /// (text before the first call, [(name, arguments)]) from what the model wrote.
    static func parseCalls(_ text: String) -> (String, [(String, Rec)]) {
        var calls: [(String, Rec)] = []
        let rx = Rx.re(CALL)
        for m in rx.matches(in: text, range: NSRange(text.startIndex..., in: text)) {
            guard let n = Range(m.range(at: 1), in: text), let b = Range(m.range(at: 2), in: text) else { continue }
            var p = ArgsParser(String(text[b]))
            let args = (try? p.objBody(end: nil)) ?? [:]
            calls.append((String(text[n]), args))
        }
        if let cut = text.range(of: "<|tool_call>") { return (String(text[..<cut.lowerBound]), calls) }
        return (text, calls)
    }

    /// Reads Gemma's argument notation: key:value pairs, strings between <|"|> marks, numbers, true/false/null, [..] and {..}.
    struct ArgsParser {
        struct Bad: Error {}
        let s: [Character]
        var i = 0
        let q = Array(GemmaPrompt.Q)
        init(_ str: String) { s = Array(str) }

        func at(_ p: [Character]) -> Bool { i + p.count <= s.count && Array(s[i..<i + p.count]) == p }
        mutating func ws() { while i < s.count, " \n\t\r".contains(s[i]) { i += 1 } }

        mutating func objBody(end: Character?) throws -> Rec {
            var out: Rec = [:]
            while true {
                ws()
                if i >= s.count || (end != nil && s[i] == end!) { return out }
                var key: String
                if at(q) { key = try string() } else {
                    guard s[i] == "_" || s[i].isLetter, s[i].isASCII else { throw Bad() }
                    var j = i
                    while j < s.count, s[j].isASCII, s[j].isLetter || s[j].isNumber || s[j] == "_" || s[j] == "-" { j += 1 }
                    key = String(s[i..<j]); i = j
                }
                ws()
                guard i < s.count, s[i] == ":" else { throw Bad() }
                i += 1
                out[key] = try value()
                ws()
                if i < s.count, s[i] == "," { i += 1 }
            }
        }

        mutating func string() throws -> String {
            i += q.count
            var j = i
            while j + q.count <= s.count, Array(s[j..<j + q.count]) != q { j += 1 }
            guard j + q.count <= s.count else { throw Bad() }
            let v = String(s[i..<j]); i = j + q.count
            return v
        }

        mutating func value() throws -> Any {
            ws()
            if at(q) { return try string() }
            if i < s.count, s[i] == "{" { i += 1; let v = try objBody(end: "}"); i += 1; return v }
            if i < s.count, s[i] == "[" {
                i += 1
                var out: [Any] = []
                while true {
                    ws()
                    if i >= s.count { throw Bad() }
                    if s[i] == "]" { i += 1; return out }
                    out.append(try value())
                    ws()
                    if i < s.count, s[i] == "," { i += 1 }
                }
            }
            var j = i
            while j < s.count, !",}]".contains(s[j]) { j += 1 }
            guard j > i else { throw Bad() }
            let w = pyStrip(String(s[i..<j])); i = j
            if w == "true" || w == "false" { return w == "true" }
            if w == "null" { return NSNull() }
            if let n = Int(w) { return n }
            if let d = Double(w) { return d }
            return pyStrip(w, "\"")
        }
    }
}
