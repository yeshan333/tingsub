import Foundation
import MLX
import MLXLLM
import MLXLMCommon
import MLXHuggingFace
import Tokenizers

struct Request: Decodable, Sendable {
    let tokens: [Int]
}

struct Response: Encodable, Sendable {
    let text: String
    let tokens: [Int]
    let native_ms: Double
}

func emit<T: Encodable>(_ value: T) throws {
    FileHandle.standardOutput.write(try JSONEncoder().encode(value) + Data([10]))
}

@main struct TranslationPilot {
    static func main() async throws {
        guard CommandLine.arguments.count == 2 else {
            throw NSError(domain: "Usage: TranslationPilot MODEL_DIRECTORY", code: 1)
        }
        let container = try await LLMModelFactory.shared.loadContainer(
            from: URL(fileURLWithPath: CommandLine.arguments[1]),
            using: #huggingFaceTokenizerLoader()
        )
        try emit(["ready": true])
        while let line = readLine() {
            do {
                let request = try JSONDecoder().decode(Request.self, from: Data(line.utf8))
                let response = try await container.perform(values: request) { context, request in
                    let started = ContinuousClock.now
                    // Identical prompt token IDs from the pinned Python tokenizer; fresh KV per call.
                    let result = try MLXLMCommon.generate(
                        input: LMInput(tokens: MLXArray(request.tokens)),
                        parameters: GenerateParameters(maxTokens: 256, temperature: 0),
                        context: context, didGenerate: { (_: [Int]) in .more }
                    )
                    let duration = started.duration(to: .now).components
                    return Response(text: result.output, tokens: result.tokenIds,
                                    native_ms: (Double(duration.seconds) + Double(duration.attoseconds) / 1e18) * 1000)
                }
                try emit(response)
            } catch {
                try emit(["error": String(describing: error)])
            }
        }
    }
}
