import Speech
import AVFoundation
import Foundation
// 用法: asr <wav>...   每个文件输出一行: 路径\t识别文本
let locale = Locale(identifier: "zh_CN")
for path in CommandLine.arguments.dropFirst() {
  let transcriber = SpeechTranscriber(locale: locale, transcriptionOptions: [], reportingOptions: [], attributeOptions: [])
  let analyzer = SpeechAnalyzer(modules: [transcriber])
  let file = try AVAudioFile(forReading: URL(fileURLWithPath: path))
  let collect = Task { () -> String in
    var s = ""
    for try await r in transcriber.results { s += String(r.text.characters) }
    return s
  }
  if let last = try await analyzer.analyzeSequence(from: file) { try await analyzer.finalizeAndFinish(through: last) } else { await analyzer.cancelAndFinishNow() }
  let text = try await collect.value
  print("\(path)\t\(text)")
}
