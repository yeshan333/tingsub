import Foundation
import WhisperKit

struct Request: Decodable {
    let path: String
    let language: String
    let default_gates: Bool?
}

func emit(_ value: [String: Any]) throws {
    let data = try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    FileHandle.standardOutput.write(data + Data([10]))
}

@main struct ASRPilot {
    static func main() async throws {
        guard CommandLine.arguments.count == 3 else {
            throw NSError(domain: "Usage: ASRPilot MODEL_DIRECTORY TOKENIZER_DIRECTORY", code: 1)
        }
        let began = ContinuousClock.now
        let pipe = try await WhisperKit(WhisperKitConfig(
            modelFolder: CommandLine.arguments[1],
            tokenizerFolder: URL(fileURLWithPath: CommandLine.arguments[2]),
            verbose: false, logLevel: .none, prewarm: false, load: true, download: false
        ))
        try emit(["ready": true, "load_seconds": seconds(began.duration(to: .now))])
        while let line = readLine() {
            do {
                let request = try JSONDecoder().decode(Request.self, from: Data(line.utf8))
                let started = ContinuousClock.now
                let results = try await pipe.transcribe(audioPath: request.path, decodeOptions: DecodingOptions(
                    language: request.language, temperature: 0, temperatureFallbackCount: 0,
                    sampleLength: 128, topK: 1, detectLanguage: false,
                    skipSpecialTokens: true, withoutTimestamps: true,
                    windowClipTime: 0,
                    compressionRatioThreshold: request.default_gates == true ? 2.4 : nil,
                    logProbThreshold: request.default_gates == true ? -1 : nil,
                    firstTokenLogProbThreshold: request.default_gates == true ? -1.5 : nil,
                    noSpeechThreshold: request.default_gates == true ? 0.6 : nil,
                    concurrentWorkerCount: 1
                ))
                let segments = results.flatMap(\.segments).map { segment -> [String: Any] in
                    ["text": segment.text, "avg_logprob": segment.avgLogprob,
                     "no_speech_prob": segment.noSpeechProb, "compression_ratio": segment.compressionRatio]
                }
                try emit(["text": results.map(\.text).joined(separator: " "), "segments": segments,
                          "language": request.language, "native_ms": seconds(started.duration(to: .now)) * 1000])
            } catch {
                try emit(["error": String(describing: error)])
            }
        }
    }
}

func seconds(_ duration: Duration) -> Double {
    Double(duration.components.seconds) + Double(duration.components.attoseconds) / 1e18
}
