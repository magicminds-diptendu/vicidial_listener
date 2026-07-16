const express = require("express");

const app = express();
const PORT = process.env.PORT || 3000;

// Parse JSON body
app.use(express.json());

// Parse form-urlencoded body
app.use(express.urlencoded({ extended: true }));

app.post("/webhook", (req, res) => {
  console.log("=================================");
  console.log("New Request Received");
  console.log("Time:", new Date().toISOString());
  console.log("Headers:", req.headers);
  console.log("Body:", req.body);
  console.log("=================================");

  res.status(200).json({
    success: true,
    message: "Request received",
    receivedData: req.body,
  });
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
