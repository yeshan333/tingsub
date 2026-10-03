// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "TingSubNativePilot",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/argmaxinc/argmax-oss-swift.git", revision: "f4e5d6be37ec820614fb0d72037e76c22d4c16f7"),
        .package(url: "https://github.com/ml-explore/mlx-swift-lm.git", revision: "55db72131169e2af11ba86eac202aeb654a7ab1a"),
        .package(url: "https://github.com/huggingface/swift-transformers", exact: "1.3.0"),
    ],
    targets: [
        .executableTarget(name: "ASRPilot", dependencies: [
            .product(name: "WhisperKit", package: "argmax-oss-swift"),
        ]),
        .executableTarget(name: "TranslationPilot", dependencies: [
            .product(name: "MLXLLM", package: "mlx-swift-lm"),
            .product(name: "MLXLMCommon", package: "mlx-swift-lm"),
            .product(name: "MLXHuggingFace", package: "mlx-swift-lm"),
            .product(name: "Tokenizers", package: "swift-transformers"),
        ]),
    ]
)
