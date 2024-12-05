import yfinance as yf
import backtrader as bt
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QComboBox, QLineEdit, QLabel, QDateEdit, QMessageBox
from PyQt5.QtCore import QDate, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon
import sys
import numpy as np
from PyQt5.QtWidgets import QDialog, QScrollArea,   QTextEdit, QPushButton
import json
from PyQt5.QtWidgets import QFileDialog
from reportlab.pdfgen import canvas
from matplotlib.backends.backend_pdf import PdfPages
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak  # PageBreak import here
from reportlab.lib.styles import getSampleStyleSheet
import os
 
# Corrected SMAStrategy class
class SMAStrategy(bt.Strategy):
    def __init__(self):
        self.short_sma = bt.indicators.SimpleMovingAverage(self.data.close, period=50)
        self.long_sma = bt.indicators.SimpleMovingAverage(self.data.close, period=200)
        self.equity_curve = []  # Store portfolio values

    def next(self):
        # Track portfolio value
        self.equity_curve.append(self.broker.getvalue())

        # Buy when short SMA crosses above long SMA
        if self.short_sma > self.long_sma:
            if not self.position:
                self.buy()
        # Sell when short SMA crosses below long SMA
        elif self.short_sma < self.long_sma:
            if self.position:
                self.sell()


# Function to calculate Sharpe Ratio
def calculate_sharpe_ratio(returns, risk_free_rate=0):
    if len(returns) == 0:
        return np.nan
    mean_return = np.mean(returns)
    std_return = np.std(returns)
    return (mean_return - risk_free_rate) / std_return if std_return != 0 else np.nan

# Function to calculate Max Drawdown
def calculate_max_drawdown(equity_curve):
    drawdowns = []
    peak = equity_curve[0]
    for value in equity_curve:
        peak = max(peak, value)
        drawdowns.append((peak - value) / peak)
    return max(drawdowns) if drawdowns else 0

# PyQt5 GUI class
 

# Updated BacktestWindow class
class BacktestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TradeWhiz")
        self.setGeometry(100, 100, 800, 600)
        self.setWindowIcon(QIcon("logo.ico"))

        # Layout
        self.layout = QVBoxLayout()

        # Stock Selection
        self.stock_label = QLabel("Select Stock:")
        self.layout.addWidget(self.stock_label)
    
        # Dropdown for pre-defined stocks
        self.stock_combobox = QComboBox()
        self.stock_combobox.addItems([
            "AAPL", "GOOGL", "AMZN", "MSFT", "TSLA", "NFLX", "META", "NVDA", "SPY", "QQQ",
            "BABA", "AMZN", "INTC", "AMD", "IBM", "DIS", "GS", "WMT", "V", "MA", "PYPL",
            "PFE", "JNJ", "MS", "T", "KO", "PEP", "NVDA", "MCD", "ORCL", "BA", "CAT",
            "UNH", "CVX", "XOM", "ADBE", "WFC", "GS", "GE", "MRK", "ABT", "LLY", "MDT"
        ])
        self.layout.addWidget(self.stock_combobox)
    
        # Input box for manual stock ticker
        self.manual_ticker_label = QLabel("Or Enter Stock Ticker:")
        self.layout.addWidget(self.manual_ticker_label)
        self.manual_ticker_input = QLineEdit()
        self.layout.addWidget(self.manual_ticker_input)

        # Date Range Selection
        self.start_date_label = QLabel("Start Date:")
        self.layout.addWidget(self.start_date_label)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate(2010, 1, 1))
        self.layout.addWidget(self.start_date_edit)

        self.end_date_label = QLabel("End Date:")
        self.layout.addWidget(self.end_date_label)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate())
        self.layout.addWidget(self.end_date_edit)

        # SMA Parameters
        self.short_sma_label = QLabel("Short SMA Period:")
        self.layout.addWidget(self.short_sma_label)
        self.short_sma_input = QLineEdit("50")
        self.layout.addWidget(self.short_sma_input)

        self.long_sma_label = QLabel("Long SMA Period:")
        self.layout.addWidget(self.long_sma_label)
        self.long_sma_input = QLineEdit("200")
        self.layout.addWidget(self.long_sma_input)

        # Starting Cash Position
        self.starting_cash_label = QLabel("Starting Cash ($):")
        self.layout.addWidget(self.starting_cash_label)
        self.starting_cash_input = QLineEdit("100000")
        self.layout.addWidget(self.starting_cash_input)

        # Backtest Button
        self.run_button = QPushButton("Run TradeWhiz")
        self.run_button.setStyleSheet("background-color: #0d47a1; color: white; font-weight: bold;")
        self.run_button.clicked.connect(self.run_backtest)
        self.layout.addWidget(self.run_button)

        # Save Report Button
        self.save_report_button = QPushButton("Save Report")
        self.save_report_button.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.save_report_button.clicked.connect(self.save_report)
        self.layout.addWidget(self.save_report_button)
        self.save_report_button.setEnabled(False)  # Initially disabled

        # Help Button
        self.help_button = QPushButton("?")
        self.help_button.setStyleSheet("font-weight: bold; background-color: lightgray;")
        self.help_button.clicked.connect(self.show_help)
        self.layout.addWidget(self.help_button, alignment=Qt.AlignRight)

        # Results
        self.results_label = QLabel("Results:")
        self.layout.addWidget(self.results_label)

        self.portfolio_label = QLabel("Outcome Portfolio Value: N/A")
        self.layout.addWidget(self.portfolio_label)

        self.drawdown_label = QLabel("Max Drawdown: N/A")
        self.layout.addWidget(self.drawdown_label)

        self.sharpe_label = QLabel("Sharpe Ratio: N/A")
        self.layout.addWidget(self.sharpe_label)

        # Graph for Equity Curve
        self.figure = plt.Figure()
        self.equity_canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.equity_canvas)

        # Graph for Stock Price and SMAs
        self.figure_price = plt.Figure()
        self.price_canvas = FigureCanvas(self.figure_price)
        self.layout.addWidget(self.price_canvas)

        # About Button
        self.about_button = QPushButton("About")
        self.about_button.setStyleSheet("background-color: #0d47a1; color: white; font-weight: bold;")
        self.about_button.clicked.connect(self.show_about)
        self.layout.addWidget(self.about_button)
        
        self.load_settings()
        self.start_date_edit.dateChanged.connect(self.save_settings)
        self.end_date_edit.dateChanged.connect(self.save_settings)
        self.stock_combobox.currentIndexChanged.connect(self.save_settings)

        self.manual_ticker_input.textChanged.connect(self.save_settings)
        self.short_sma_input.textChanged.connect(self.save_settings)
        self.long_sma_input.textChanged.connect(self.save_settings)
        self.starting_cash_input.textChanged.connect(self.save_settings)

        

        # Set the layout
        self.setLayout(self.layout)

    def update_results(self, portfolio_value, sharpe_ratio, max_drawdown, equity_curve, price_data):
        # Re-enable the Run Backtest button and enable Save Report
        self.run_button.setEnabled(True)
        self.save_report_button.setEnabled(True)

        if portfolio_value is None:
            self.results_label.setText("Error: Backtest failed. Check logs for details.")
            return

        # Update result labels
        self.portfolio_label.setText(f"Portfolio Value: {portfolio_value:.2f}")
        self.sharpe_label.setText(f"Sharpe Ratio: {sharpe_ratio:.2f}")
        self.drawdown_label.setText(f"Max Drawdown: {max_drawdown:.2f}")

        # Plot Equity Curve
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(equity_curve, label="Equity Curve")
        ax.set_title("Equity Curve")
        ax.set_xlabel("Time")
        ax.set_ylabel("Portfolio Value")
        ax.legend()
        self.equity_canvas.draw()

        # Plot Price with SMAs
        self.figure_price.clear()
        ax_price = self.figure_price.add_subplot(111)
        ax_price.plot(price_data["close"], label="Close Price", alpha=0.8)
        ax_price.plot(price_data["short_sma"], label="Short SMA", linestyle="--")
        ax_price.plot(price_data["long_sma"], label="Long SMA", linestyle="--")
        ax_price.set_title("Price with Short and Long SMAs")
        ax_price.set_xlabel("Date")
        ax_price.set_ylabel("Price")
        ax_price.legend()
        self.price_canvas.draw()

        self.results_label.setText("TradeWhiz Backtest Complete!")


    def save_report(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Report", "", "PDF Files (*.pdf)")
        if not file_path:
            return
    
        # Backtest parameters to include in the report
        manual_ticker = self.manual_ticker_input.text().strip()
        stock_symbol = manual_ticker if manual_ticker else self.stock_combobox.currentText()
        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")
        short_sma_period = int(self.short_sma_input.text())
        long_sma_period = int(self.long_sma_input.text())
        starting_cash = float(self.starting_cash_input.text())
    
        try:
            # Temporary file paths for high-resolution graphs
            equity_curve_path = "equity_curve_high_res.png"
            sma_curve_path = "sma_curve_high_res.png"
    
            # Save high-resolution graphs
            self.figure.savefig(equity_curve_path, dpi=300, bbox_inches='tight')  # High DPI for sharp text
            self.figure_price.savefig(sma_curve_path, dpi=300, bbox_inches='tight')  # High DPI for sharp text
    
            # Create a PDF document
            pdf = SimpleDocTemplate(
                file_path, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=60, bottomMargin=30
            )
    
            # Styles
            styles = getSampleStyleSheet()
            title_style = styles['Title']
            heading_style = styles['Heading2']
            normal_style = styles['BodyText']
    
            # Title Page
            elements = []
    
            title = Paragraph("TradeWhiz 9.11 Backtest Report", title_style)
            subtitle = Paragraph("© SIG Labs 2024 | by peterdeceuster.uk", normal_style)
            logo = Image("logo.png", width=100, height=50)  # Ensure logo.png exists in the same directory
    
            elements.append(logo)
            elements.append(Spacer(1, 12))
            elements.append(title)
            elements.append(Spacer(1, 12))
            elements.append(subtitle)
            elements.append(Spacer(1, 24))
    
            # Backtest Parameters
            elements.append(Paragraph("Backtest Parameters", heading_style))
            params_data = [
                ["Parameter", "Value"],
                ["Stock Ticker", stock_symbol],
                ["Start Date", start_date],
                ["End Date", end_date],
                ["Short SMA Period", short_sma_period],
                ["Long SMA Period", long_sma_period],
                ["Starting Cash ($)", f"${starting_cash:,.2f}"]
            ]
            params_table = Table(params_data, hAlign="LEFT")
            params_table.setStyle(
                TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ])
            )
            elements.append(params_table)
            elements.append(Spacer(1, 24))
    
            # Add Graphs - One per page
            elements.append(Paragraph("Equity Curve", heading_style))
            equity_curve_image = Image(equity_curve_path)
            
            # Resize the image proportionally to fit within the page (max size)
            max_width = 500  # Max width for the image
            max_height = 690  # Max height for the image
            # Calculate aspect ratio to maintain the image proportions
            aspect_ratio = equity_curve_image.imageWidth / equity_curve_image.imageHeight
            if equity_curve_image.imageWidth > max_width:
                equity_curve_image.drawWidth = max_width
                equity_curve_image.drawHeight = max_width / aspect_ratio
            else:
                equity_curve_image.drawHeight = min(equity_curve_image.imageHeight, max_height)
                equity_curve_image.drawWidth = equity_curve_image.drawHeight * aspect_ratio
            
            elements.append(equity_curve_image)
    
            # Ensure the graph is on a new page
            elements.append(Spacer(1, 12))  # Adjust spacing if necessary
            elements.append(PageBreak())  # This adds a new page after the equity curve graph
    
            elements.append(Paragraph("Price with Short and Long SMAs", heading_style))
            sma_curve_image = Image(sma_curve_path)
            
            # Resize the image for SMAs graph similarly
            if sma_curve_image.imageWidth > max_width:
                sma_curve_image.drawWidth = max_width
                sma_curve_image.drawHeight = max_width / (sma_curve_image.imageWidth / sma_curve_image.imageHeight)
            else:
                sma_curve_image.drawHeight = min(sma_curve_image.imageHeight, max_height)
                sma_curve_image.drawWidth = sma_curve_image.drawHeight * (sma_curve_image.imageWidth / sma_curve_image.imageHeight)
    
            elements.append(sma_curve_image)
    
            # Build PDF
            pdf.build(elements)
    
            QMessageBox.information(self, "Report Saved", f"Report saved to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save report: {str(e)}")
            
 
    def save_settings(self):
        # Collect settings
        settings = {
            "start_date": self.start_date_edit.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date_edit.date().toString("yyyy-MM-dd"),
            "stock_symbol": self.stock_combobox.currentText(),
            "manual_ticker": self.manual_ticker_input.text(),
            "short_sma": self.short_sma_input.text(),
            "long_sma": self.long_sma_input.text(),
            "starting_cash": self.starting_cash_input.text(),
        }
    
        # Determine file path
        settings_file_path = os.path.join(os.getcwd(), "gui_settings.json")
        print(f"Saving settings to: {settings_file_path}")  # Debug log
    
        # Save settings to file
        try:
            with open(settings_file_path, "w") as f:
                json.dump(settings, f, indent=4)
            print("Settings saved successfully:", settings)
        except Exception as e:
            print(f"Failed to save settings: {e}")
    
    def load_settings(self):
        print("Loading settings...")  # Debug log
        try:
            with open("gui_settings.json", "r") as f:
                settings = json.load(f)
            print("Loaded settings:", settings)  # Debug log
    
            # Apply settings to GUI components
            self.start_date_edit.setDate(QDate.fromString(settings.get("start_date", "2022-01-01"), "yyyy-MM-dd"))
            self.end_date_edit.setDate(QDate.fromString(settings.get("end_date", "2022-12-31"), "yyyy-MM-dd"))
            self.stock_combobox.setCurrentText(settings.get("stock_symbol", "AAPL"))
            self.manual_ticker_input.setText(settings.get("manual_ticker", ""))
            self.short_sma_input.setText(settings.get("short_sma", "50"))
            self.long_sma_input.setText(settings.get("long_sma", "200"))
            self.starting_cash_input.setText(settings.get("starting_cash", "100000"))
    
            print("Settings applied successfully!")
        except FileNotFoundError:
            print("No saved settings found. Using default settings.")
        except Exception as e:
            print(f"Failed to load settings: {e}")
        
            

            

    def run_backtest(self):
        self.run_button.setEnabled(False)
        self.results_label.setText("Running backtest...")
    
        # Use manual ticker if provided, otherwise use dropdown
        manual_ticker = self.manual_ticker_input.text().strip()
        stock_symbol = manual_ticker if manual_ticker else self.stock_combobox.currentText()
        
        if manual_ticker and not manual_ticker.isalnum():
            QMessageBox.warning(self, "Invalid Ticker", "The entered stock ticker is invalid. Please use a valid ticker symbol.")
            self.run_button.setEnabled(True)
            return

    
        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")
        short_sma_period = int(self.short_sma_input.text())
        long_sma_period = int(self.long_sma_input.text())
        starting_cash = float(self.starting_cash_input.text())
    
        self.backtest_thread = BacktestThread(stock_symbol, start_date, end_date, short_sma_period, long_sma_period, starting_cash)
        self.backtest_thread.result_signal.connect(self.update_results)
        self.backtest_thread.start()

    def show_about(self):
            # Show an About dialog with clickable links
            about_msg = QMessageBox(self)
            about_msg.setWindowTitle("About")
            about_msg.setIcon(QMessageBox.Information)
            about_msg.setText("(c) TradeWhiz 9.11 2024 Peter De Ceuster SIG Labs")
            about_msg.setInformativeText(
                '<a href="https://buymeacoffee.com/siglabo">Buy Me a Coffee</a><br>'
                '<a href="https://peterdeceuster.uk/index2">Visit My Website</a>'
            )
            about_msg.setStandardButtons(QMessageBox.Ok)
            about_msg.setTextFormat(Qt.RichText)
            about_msg.exec_()
            
            
            
 
    
    def show_help(self):
        # Create a QDialog for the help content
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("Help - TradeWhiz")
        help_dialog.setGeometry(100, 100, 800, 600)
        help_dialog.setWindowModality(Qt.ApplicationModal)
        help_dialog.setMinimumSize(800, 600)  # Minimum dimensions for the dialog
    
        # Scrollable area for help text
        scroll_area = QScrollArea(help_dialog)
        scroll_area.setWidgetResizable(True)
    
        # Help text content
        help_content = QTextEdit()
        help_content.setReadOnly(True)  # Disable editing
        help_content.setHtml("""
        <h1>TradeWhiz Help Guide</h1>
<p>Welcome to TradeWhiz! This guide explains the key features, metrics, and settings to help you make the most of your backtesting experience.</p>

<h2>Stock Selection</h2>
<ul>
    <li><b>Dropdown:</b> Select from a list of popular stock tickers.</li>
    <li><b>Manual Entry:</b> Enter any valid stock ticker in the input box.</li>
</ul>

<h2>Date Range</h2>
<p>Specify the start and end dates for your backtest. Ensure there is sufficient historical data for the chosen SMA periods.</p>

<h2>Short SMA Period</h2>
<p>A short Simple Moving Average (SMA) reacts quickly to price changes. It is typically used to identify short-term trends.</p>

<h2>Long SMA Period</h2>
<p>A long SMA reacts more slowly to price changes, providing a broader view of overall trends.</p>

<h2>Sharpe Ratio</h2>
<p>The Sharpe Ratio measures risk-adjusted returns. Higher values indicate better performance relative to risk.</p>
<ul>
    <li><b>Low Value:</b> A Sharpe Ratio below 1 is generally considered low, suggesting that returns are not significantly greater than the risk taken.</li>
    <li><b>High Value:</b> A Sharpe Ratio above 2 is usually considered good, indicating that the strategy provides good returns relative to its risk.</li>
    <li><b>Excellent Value:</b> A Sharpe Ratio above 3 is exceptional, suggesting a highly efficient investment strategy.</li>
</ul>
<p><b>Backtesting Implications:</b> A higher Sharpe Ratio suggests that your strategy is providing consistent returns with lower risk. When optimizing your strategy, aim for a balance of returns and risk management. Extremely high Sharpe Ratios may sometimes indicate overfitting, especially with small datasets.</p>

<h2>Max Drawdown</h2>
<p>Max Drawdown represents the largest percentage loss from a portfolio peak, showing the worst possible loss in a given period.</p>
<ul>
    <li><b>Low Value:</b> A Max Drawdown less than 20% is typically considered low, indicating a strategy that does not expose you to significant losses.</li>
    <li><b>High Value:</b> A Max Drawdown above 30% is considered high, indicating that the strategy might be too risky.</li>
    <li><b>Excellent Value:</b> A Max Drawdown of less than 10% is ideal, suggesting minimal risk exposure.</li>
</ul>
<p><b>Backtesting Implications:</b> A lower Max Drawdown value is a sign of a more stable strategy. However, strategies with very low drawdowns may sacrifice potential returns. Aim for a drawdown within a range that aligns with your risk tolerance.</p>

<h2>Short and Long SMA Strategy</h2>
<p>The Short and Long SMA strategy helps identify the ideal entry and exit points for trades based on market trends.</p>
<h3>Short SMA</h3>
<p>The Short SMA reacts more quickly to recent price movements and is typically used to capture short-term trends. A smaller short SMA (like 5–50 periods) makes the strategy more sensitive to market fluctuations, leading to more frequent trades but possibly more false signals.</p>

<h3>Long SMA</h3>
<p>The Long SMA smoothens out price data over a longer period, providing a more stable trend indication. A longer period (like 100–300 periods) leads to fewer trades, focusing on broader market trends and potentially avoiding short-term market noise.</p>

<h3>Backtesting Implications</h3>
<p>Adjusting SMA values can drastically affect your backtest results. A very small short SMA and a very long long SMA might result in missing good entry points, while extreme values may overfit the strategy to historical data. It’s recommended to experiment with different SMA values to find an optimal balance for both backtesting accuracy and practical implementation.</p>

<h2>Planning Short and Long SMA Strategy in Real Life</h2>
<h3>1. Define Your Trading Goals</h3>
<ul>
    <li><b>Short-Term vs Long-Term:</b> Decide whether you're trading for short-term gains or long-term trends. The Short SMA is more suited to short-term traders who want to react quickly to market fluctuations, while the Long SMA suits long-term investors who want to capture broader market trends.</li>
    <li><b>Short-Term Goal:</b> If you are aiming for quick gains (e.g., day trading or swing trading), a shorter Short SMA (like 5–20 periods) might work better.</li>
    <li><b>Long-Term Goal:</b> If you are more focused on stable, long-term investments (e.g., position trading), a longer Short SMA (like 50–100 periods) and a longer Long SMA (100–200 periods) might be more appropriate.</li>
</ul>

<h3>2. Understand the Market Context</h3>
<p>The Short and Long SMA strategy works best in trending markets. In sideways markets, this strategy might lead to more false signals and choppy results. In trending markets, the strategy will help you enter trades at the right moments when the short-term price trend confirms the long-term market trend.</p>

<h3>3. Set Realistic Expectations</h3>
<ul>
    <li><b>Risk Management:</b> Set stop-losses and take-profits based on the volatility of the asset and market conditions. For example, use tight stop-losses with a Short SMA and wider stop-losses with a Long SMA.</li>
</ul>

<h3>4. Backtest and Optimize Parameters</h3>
<p>Every asset behaves differently, and there's no one-size-fits-all when it comes to SMA periods. Optimize your strategy for the asset's volatility, e.g., shorter SMAs for volatile stocks and longer SMAs for stable assets.</p>

<h3>5. Consider Other Indicators for Confirmation</h3>
<p>To avoid over-reliance on SMAs alone, use additional indicators such as volume, RSI, or MACD to confirm signals.</p>

<h3>6. Trade Execution and Psychology</h3>
<ul>
    <li><b>Real-Time Execution:</b> Ensure you can monitor the market and execute trades swiftly. Set alerts for SMA crossovers.</li>
    <li><b>Emotional Control:</b> Stick to your strategy and avoid letting emotions drive your trading decisions.</li>
</ul>

<h2>Equity Curve</h2>
<p>A graph showing the portfolio value over time. It helps visualize performance and trends.</p>

<h2>How to Use TradeWhiz</h2>
<ol>
    <li>Select a stock ticker or enter a manual ticker.</li>
    <li>Set the desired date range and SMA periods.</li>
    <li>Enter the starting cash amount.</li>
    <li>Click "Run TradeWhiz" to perform the backtest.</li>
    <li>Analyze the results, including the Sharpe Ratio, Max Drawdown, and Equity Curve.</li>
</ol>

<p><b>Happy Backtesting with TradeWhiz!</b></p>

        """)
    
        # Add the help content to the scroll area
        scroll_area.setWidget(help_content)
    
        # Add Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(help_dialog.accept)
    
        # Layout for the dialog
        dialog_layout = QVBoxLayout()
        dialog_layout.addWidget(scroll_area)
        dialog_layout.addWidget(close_button)
    
        help_dialog.setLayout(dialog_layout)
        help_dialog.showMaximized()
        help_dialog.exec_()  # Show the dialog
        
 

class BacktestThread(QThread):
    result_signal = pyqtSignal(object, object, object, object, object)  # Added price_data to the signal

    def __init__(self, stock_symbol, start_date, end_date, short_sma_period, long_sma_period, starting_cash):
        super().__init__()
        self.stock_symbol = stock_symbol
        self.start_date = start_date
        self.end_date = end_date
        self.short_sma_period = short_sma_period
        self.long_sma_period = long_sma_period
        self.starting_cash = starting_cash
     
 



    def run(self):
        portfolio_value, sharpe_ratio, max_drawdown, equity_curve, price_data = self.backtest(
            self.stock_symbol, self.start_date, self.end_date, self.short_sma_period, self.long_sma_period, self.starting_cash
        )
        self.result_signal.emit(portfolio_value, sharpe_ratio, max_drawdown, equity_curve, price_data)

    def backtest(self, stock_symbol, start_date, end_date, short_sma_period, long_sma_period, starting_cash):
        # Download data from Yahoo Finance
        data = yf.download(stock_symbol, start=start_date, end=end_date)
    
        if len(data) < long_sma_period:
            return None, None, None, None, None
    
        # If the DataFrame has a MultiIndex, flatten it
        if isinstance(data.columns, pd.MultiIndex):
            # Flatten the MultiIndex and use the first level of the index (e.g., 'Adj Close', 'Close', etc.)
            data.columns = [col[0] for col in data.columns]
    
        # Rename columns to standardize them
        data = data.rename(columns={
            'Adj Close': 'close', 
            'Open': 'open', 
            'High': 'high', 
            'Low': 'low', 
            'Volume': 'volume'
        })
    
        # Ensure "close" column exists
        if "close" not in data.columns:
            raise KeyError("The 'close' column is missing from the downloaded data. Verify the data source.")
    
        # Calculate SMAs
        data["short_sma"] = data["close"].rolling(window=short_sma_period).mean()
        data["long_sma"] = data["close"].rolling(window=long_sma_period).mean()
    
        # Prepare data feed for Backtrader
        data_feed = bt.feeds.PandasData(dataname=data)
    
        # Initialize Cerebro
        cerebro = bt.Cerebro()
        cerebro.adddata(data_feed)
        cerebro.addstrategy(SMAStrategy)
        cerebro.addobserver(bt.observers.Value)  # Track portfolio value
    
        # Broker settings
        cerebro.broker.set_cash(starting_cash)
        cerebro.broker.setcommission(commission=0.001)
        cerebro.addsizer(bt.sizers.FixedSize, stake=10)
    
        # Run backtest
        results = cerebro.run()
    
        # Get portfolio value and equity curve
        strategy = results[0]  # Access the strategy instance
        equity_curve = strategy.equity_curve
        portfolio_value = cerebro.broker.getvalue()
        sharpe_ratio = calculate_sharpe_ratio(np.diff(equity_curve))
        max_drawdown = calculate_max_drawdown(equity_curve)
    
        # Extract only the required columns for price_data
        price_data = data[["close", "short_sma", "long_sma"]]
    
        return portfolio_value, sharpe_ratio, max_drawdown, equity_curve, price_data
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BacktestWindow()
    window.show()
    window.showMaximized()

    sys.exit(app.exec_())           