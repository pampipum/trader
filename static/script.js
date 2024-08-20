$(document).ready(function () {
  // Fetch symbols
  $.get("/fetch_symbols", function (data) {
    const cryptoSymbols = data.filter((symbol) => symbol.includes("/"));
    const marketSymbols = data.filter((symbol) => !symbol.includes("/"));
    const favoriteSymbols = [
      "VIX",
      "SPX",
      "QQQ",
      "US10Y",
      "US02Y",
      "US30Y",
      "GOLD",
      "OIL_CRUD",
    ];

    $("#symbol-type").change(function () {
      const symbolType = $(this).val();
      let symbols;

      if (symbolType === "search") {
        $("#symbol-dropdown-container").hide();
        $("#search-container").show();
        return;
      } else {
        $("#symbol-dropdown-container").show();
        $("#search-container").hide();
      }

      if (symbolType === "crypto") {
        symbols = cryptoSymbols;
      } else if (symbolType === "market") {
        symbols = marketSymbols;
      } else if (symbolType === "favorite") {
        symbols = favoriteSymbols;
      }

      $("#symbol").empty().append('<option value="">Select...</option>');
      symbols.forEach((symbol) => {
        $("#symbol").append(`<option value="${symbol}">${symbol}</option>`);
      });
    });

    // Trigger change to populate initial dropdown
    $("#symbol-type").trigger("change");
  });

  // Search functionality
  $("#search-button").click(function () {
    const query = $("#search-input").val();
    if (query) {
      $.get("/search_ticker", { query: query }, function (data) {
        $("#search-results").empty();
        if (data.length > 0) {
          data.forEach((ticker) => {
            $("#search-results").append(
              `<div class="search-result" data-symbol="${ticker}">${ticker}</div>`
            );
          });
        } else {
          $("#search-results").append("<p>No results found.</p>");
        }
      });
    }
  });

  // Handle search result selection
  $(document).on("click", ".search-result", function () {
    const selectedSymbol = $(this).data("symbol");
    $("#symbol").val(selectedSymbol);
    $("#search-results").empty();
  });

  $("#analyze-btn").click(function () {
    const symbol = $("#symbol").val() || $("#search-input").val();
    const model = $("#model").val();
    if (symbol) {
      // Show loading message
      $(".meta-info").show();
      $("#symbol-display").text("Loading...");
      $("#timestamp").text("Analysis in progress");
      $("#model-used").text(model);
      $("#analysis-content").html("<p>Analyzing... Please wait.</p>");

      $.post("/analyze", { symbol: symbol, model: model }, function (data) {
        if (data.error) {
          $(".meta-info").show();
          $("#symbol-display").text(symbol);
          $("#timestamp").text("Error occurred");
          $("#model-used").text(model);
          $("#analysis-content").html(`<p>Error: ${data.error}</p>`);
        } else if (data.analysis) {
          $(".meta-info").show();
          $("#symbol-display").text(data.symbol || symbol);
          $("#timestamp").text(data.timestamp || new Date().toISOString());
          $("#model-used").text(data.model || model);

          // Convert markdown to HTML
          const converter = new showdown.Converter();
          const htmlContent = converter.makeHtml(data.analysis);

          $("#analysis-content").html(htmlContent);

          // Apply syntax highlighting
          document.querySelectorAll("pre code").forEach((block) => {
            hljs.highlightBlock(block);
          });
        } else {
          $("#analysis-content").html(
            "<p>No analysis available for this symbol.</p>"
          );
        }
      }).fail(function (jqXHR, textStatus, errorThrown) {
        $(".meta-info").show();
        $("#symbol-display").text(symbol);
        $("#timestamp").text("Error occurred");
        $("#model-used").text(model);
        $("#analysis-content").html(
          `<p>Error: ${textStatus} - ${errorThrown}</p>`
        );
      });
    } else {
      alert("Please select a symbol or enter a ticker to search.");
    }
  });

  let progressInterval;

  function startProgressCheck() {
    progressInterval = setInterval(checkProgress, 2000); // Check every 2 seconds
  }

  function stopProgressCheck() {
    clearInterval(progressInterval);
  }

  function checkProgress() {
    $.get("/market_analysis_progress", function (data) {
      updateProgressBar(data.progress);
      if (data.progress >= 100) {
        stopProgressCheck();
      }
    }).fail(function () {
      stopProgressCheck();
      $("#analysis-content").html(
        "<p>Error checking progress. Please try again.</p>"
      );
    });
  }

  function updateProgressBar(progress) {
    $("#progress-bar")
      .width(progress + "%")
      .text(progress + "%");
  }

  // Analyze market button click event
  $("#analyze-market-btn").click(function () {
    $("#analysis-content").html("<p>Analyzing market... Please wait.</p>");
    $("#progress-container").show();
    updateProgressBar(0);

    startProgressCheck();

    $.post("/analyze_market", function (data) {
      stopProgressCheck();
      let content = "";
      if (data.market_analysis) {
        content += "<h2>Market Analysis</h2>";
        content +=
          "<div class='market-analysis'>" + data.market_analysis + "</div>";
      }

      // Option to display individual analyses if needed
      if (data.individual_analyses) {
        content += "<h2>Individual Asset Analyses</h2>";
        for (let asset in data.individual_analyses) {
          content += `<h3>${asset}</h3>`;
          content +=
            "<div class='individual-analysis'>" +
            data.individual_analyses[asset].analysis +
            "</div>";
        }
      }

      $("#analysis-content").html(content);
      $("#progress-container").hide();
    }).fail(function (jqXHR, textStatus, errorThrown) {
      stopProgressCheck();
      let content = `<h2>Error in Analysis</h2>`;
      content += `<p>${textStatus} - ${errorThrown}</p>`;
      if (jqXHR.responseJSON) {
        if (jqXHR.responseJSON.error) {
          content += `<p>Error: ${jqXHR.responseJSON.error}</p>`;
        }
        if (jqXHR.responseJSON.traceback) {
          content += `<h3>Traceback</h3>`;
          content += `<pre>${jqXHR.responseJSON.traceback}</pre>`;
        }
      }
      $("#analysis-content").html(content);
      $("#progress-container").hide();
    });
  });
});
