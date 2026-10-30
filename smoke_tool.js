const { io } = require("socket.io-client");
const s = io("https://ielts-speaking-practice.onrender.com", { transports: ["polling","websocket"], timeout: 60000, reconnection: false, extraHeaders: { Origin: "https://ielts-speaking-practice-815.netlify.app" } });
let started = false, part1 = false, examiner = [];
const t0 = Date.now(); const ts = () => "[" + ((Date.now()-t0)/1000).toFixed(1) + "s] ";
s.on("connect", () => { console.log(ts() + "CONNECTED"); s.emit("start_audio", { client_id: "smoke-tool" }); });
s.on("connection_state", d => { if (d.connected && !started) { started = true; setTimeout(() => { console.log(ts() + "emit start_test(full)"); s.emit("run_ielts_tool", { tool: "start_test", args: { mode: "full" } }); }, 5000); } });
s.on("test_state", d => { if (d.part === 1) part1 = true; console.log(ts() + "[test_state] phase=" + d.phase + " part=" + d.part + " kind=" + d.kind + " q=" + d.question_index + "/" + d.question_total); });
s.on("transcription", d => { if (d.sender === "Examiner") examiner.push(d.text); });
s.on("error", d => console.log(ts() + "[error] " + JSON.stringify(d)));
setTimeout(() => {
  s.emit("stop_audio"); s.close();
  console.log(ts() + "RESULT part1=" + part1 + " examiner=\"" + examiner.join(" ").trim() + "\"");
  process.exit(part1 ? 0 : 1);
}, 30000);
