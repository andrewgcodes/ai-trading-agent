MIT license

this is a Claude-based tool using agent that retrieves real news and stock data using various tools (Perplexity, Exa, Yahoo Finance) and also has access to a basic calculator, enabling it to make precise financial calculations. It also has a SQlite db for logging trades and tracking the portfolio allocation.
The live Streamlit app is [here](https://eigensurance.replit.app/)

To run it you need to 
```!pip install yfinance exa_py anthropic```
You'll need API keys for anthropic, exa, and perplexity. no api key needed for yfinance.
