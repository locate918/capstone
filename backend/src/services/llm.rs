// LLM Integration Service
// Owner: Ben (AI Engineer)
//
// This service will:
// 1. Take a user's natural language query
// 2. Send it to Gemini API (or other LLM)
// 3. Parse the intent (category, date, location, keywords, etc.)
// 4. Call internal search endpoints
// 5. Format results conversationally
//
// Example flow:
//   User: "Any live music this Friday night?"
//   LLM interprets: category=music, date=2026-01-24, time=evening
//   Calls: GET /api/events/search?category=music
//   Returns: "I found 3 live music events Friday night: ..."
//
// Resources:
// - Gemini API docs: https://ai.google.dev/docs
// - Reqwest crate for HTTP: https://docs.rs/reqwest
//
// pub async fn query_llm(prompt: &str) -> Result<String, Box<dyn std::error::Error>> {
//     todo!()
// }
//
// pub async fn parse_user_intent(message: &str) -> Result<SearchParams, Box<dyn std::error::Error>> {
//     todo!()
// }