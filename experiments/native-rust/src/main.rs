//! Opt-in resident Rust orchestrator. Actual inference is in loopback C++ servers.
//! No downloads, remote URLs, simulated inference or production service changes.
use reqwest::blocking::{multipart, Client};
use serde_json::{json, Value};
use std::error::Error;
use std::io::{self, BufRead, Write};
use std::time::{Duration, Instant};

fn run(client: &Client, request: &Value) -> Result<Value, Box<dyn Error>> {
    let started = Instant::now();
    let mut response: Value = match request["operation"].as_str() {
        Some("asr") => {
            let path = request["path"].as_str().ok_or("missing WAV path")?;
            let language = request["language"].as_str().ok_or("missing language")?;
            if !matches!(language, "en" | "ja") {
                return Err("language must be en or ja".into());
            }
            let part = multipart::Part::bytes(std::fs::read(path)?)
                .file_name("segment.wav")
                .mime_str("audio/wav")?;
            let form = multipart::Form::new()
                .part("file", part)
                .text("language", language.to_owned())
                .text("response_format", "verbose_json")
                .text("temperature", "0")
                .text("temperature_inc", "0")
                .text("best_of", "1")
                .text("beam_size", "1")
                .text("no_timestamps", "true")
                .text("no_language_probabilities", "true");
            client
                .post("http://127.0.0.1:18766/inference")
                .multipart(form)
                .send()?
                .error_for_status()?
                .json()?
        }
        Some("translate") => {
            let tokens = request["tokens"]
                .as_array()
                .ok_or("missing prompt token IDs")?;
            if tokens.is_empty() || tokens.iter().any(|v| v.as_u64().is_none()) {
                return Err("prompt tokens must be nonempty unsigned integers".into());
            }
            client
                .post("http://127.0.0.1:18767/completion")
                .json(
                    &json!({"prompt": tokens, "n_predict": 256, "temperature": 0,
                    "seed": 0, "repeat_penalty": 1, "cache_prompt": false, "stream": false}),
                )
                .send()?
                .error_for_status()?
                .json()?
        }
        _ => return Err("unknown operation".into()),
    };
    response["native_ms"] = json!(started.elapsed().as_secs_f64() * 1000.0);
    Ok(response)
}

fn main() -> Result<(), Box<dyn Error>> {
    let client = Client::builder()
        .no_proxy()
        .timeout(Duration::from_secs(90))
        .build()?;
    let mut output = io::stdout().lock();
    writeln!(output, "{}", json!({"ready": true}))?;
    output.flush()?;
    for line in io::stdin().lock().lines() {
        let result = line
            .map_err(Box::<dyn Error>::from)
            .and_then(|line| Ok(serde_json::from_str::<Value>(&line)?))
            .and_then(|request| run(&client, &request));
        let response = result.unwrap_or_else(|error| json!({"error": error.to_string()}));
        writeln!(output, "{response}")?;
        output.flush()?;
    }
    Ok(())
}
