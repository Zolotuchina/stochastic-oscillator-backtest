import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


# Stochastic oscillator: %K = position of the close within the high-low range of the
# last `period` days, %D = `smooth_d`-day moving average of %K
def calculate_stochastic_oscillator(df, period=14, smooth_d=3):
    highest_high = df['High'].rolling(window=period).max()
    lowest_low = df['Low'].rolling(window=period).min()
    df['%K'] = 100 * (df['Close'] - lowest_low) / (highest_high - lowest_low)
    df['%D'] = df['%K'].rolling(window=smooth_d).mean()
    return df


# Long-only signals: buy (+1) when %K drops to the oversold level while flat,
# sell (-1) when %K rises to the overbought level while in a position
def generate_stochastic_signals(df, overbought=80, oversold=20):
    signals = pd.DataFrame(index=df.index)
    signals['price'] = df['Close']
    signals['Stochastic_signal'] = 0.0
    current_position = 0

    for i in range(len(signals)):
        if df['%K'].iloc[i] <= oversold and current_position == 0:
            signals.loc[signals.index[i], 'Stochastic_signal'] = 1.0
            current_position = 1

        elif df['%K'].iloc[i] >= overbought and current_position == 1:
            signals.loc[signals.index[i], 'Stochastic_signal'] = -1.0
            current_position = 0

    return signals


# Runs the signals through a simple all-in/all-out backtest with commission,
# tags each exit as stop-loss / take-profit, and reports profit and Sharpe ratio
def backtest_strategy(signals, initial_investment=1000, stop_loss_pct=0.02, take_profit_pct=0.05, commission_pct=0.01):
    capital = initial_investment
    positions = []
    cumulative_profit = []
    trade_dates = []
    stop_loss_trades = []
    take_profit_trades = []
    successful_trades = 0
    unsuccessful_trades = 0
    profit = []

    for i in range(len(signals)):
        current_price = signals['price'].iloc[i]

        if signals.loc[signals.index[i], 'Stochastic_signal'] == 1.0 and capital > 0:
            buy_price = current_price
            stop_loss = buy_price * (1 - stop_loss_pct)
            take_profit = buy_price * (1 + take_profit_pct)
            positions.append(capital / buy_price)
            capital = 0

        if signals.loc[signals.index[i], 'Stochastic_signal'] == -1.0 and positions:
            sell_value = positions[-1] * current_price
            capital += sell_value * (1 - commission_pct)
            trade_dates.append(signals.index[i])

            if current_price <= stop_loss:
                stop_loss_trades.append(signals.index[i])
                unsuccessful_trades += 1
            elif current_price >= take_profit:
                take_profit_trades.append(signals.index[i])
                successful_trades += 1
            else:
                successful_trades += 1

            positions.pop()
            profit.append(capital - initial_investment)

        cumulative_profit.append(capital + (positions[-1] * current_price if positions else 0))

    if positions:
        capital += positions[-1] * signals['price'].iloc[-1] * (1 - commission_pct)

    final_profit = capital - initial_investment
    returns = np.array(profit)

    if len(returns) < 2:
        sharpe_ratio = None
    else:
        avg_return = np.mean(returns)
        std_dev_return = np.std(returns)
        risk_free_rate = 0
        sharpe_ratio = (avg_return - risk_free_rate) / std_dev_return if std_dev_return > 0 else None

    return final_profit, profit, trade_dates, successful_trades, unsuccessful_trades, sharpe_ratio, stop_loss_trades, take_profit_trades, cumulative_profit


# Grid search over overbought/oversold thresholds, maximising the Sharpe ratio
def optimize_stochastic_parameters(df, overbought_range=(70, 90), oversold_range=(10, 30)):
    best_sharpe = float('-inf')
    best_overbought = None
    best_oversold = None

    for overbought in range(overbought_range[0], overbought_range[1] + 1):
        for oversold in range(oversold_range[0], oversold_range[1] + 1):
            signals = generate_stochastic_signals(df, overbought, oversold)
            _, _, _, _, _, sharpe_ratio, _, _, _ = backtest_strategy(signals)

            if sharpe_ratio and sharpe_ratio > best_sharpe:
                best_sharpe = sharpe_ratio
                best_overbought = overbought
                best_oversold = oversold

    return best_overbought, best_oversold, best_sharpe


# Three panels: price with trade markers, the oscillator with optimised thresholds,
# and profit per trade for the default vs optimised strategy
def plot_graphs():
    plt.figure(figsize=(14, 20))
    plt.subplot(3, 1, 1)
    plt.plot(signals_default['price'], label='Price', alpha=0.5)
    plt.plot(signals_default[signals_default['Stochastic_signal'] == 1.0].index,
        signals_default['price'][signals_default['Stochastic_signal'] == 1.0], '^', markersize=10, color='g', lw=0, label='Buy signals')
    plt.plot(signals_default[signals_default['Stochastic_signal'] == -1.0].index,
         signals_default['price'][signals_default['Stochastic_signal'] == -1.0], 'v', markersize=10, color='r', lw=0, label='Sell signals')
    plt.scatter(stop_loss_trades_default, signals_default['price'][stop_loss_trades_default], marker='x', color='black', s=100, label='Stop Loss', zorder=10)
    plt.scatter(take_profit_trades_default, signals_default['price'][take_profit_trades_default], marker='o', color='black', s=50, label='Take Profit', zorder=10)
    plt.title('Stochastic strategy, default thresholds (80 / 20)')
    plt.legend()

    plt.subplot(3, 1, 2)
    plt.plot(prices.index, prices['%K'], label='%K Line', color='blue')
    plt.plot(prices.index, prices['%D'], label='%D Line', color='red')
    plt.axhline(y=best_overbought, color='r', linestyle='--', label=f'Optimized Overbought = {best_overbought}')
    plt.axhline(y=best_oversold, color='g', linestyle='--', label=f'Optimized Oversold = {best_oversold}')
    plt.title('Stochastic oscillator with optimised thresholds')
    plt.legend()

    plt.subplot(3, 1, 3)
    dates_optimized = pd.to_datetime(trade_dates_optimized) if trade_dates_optimized else []
    dates_default = pd.to_datetime(trade_dates_default) if trade_dates_default else []
    plt.plot(dates_default, profit_default, label='Default thresholds', color='orange')
    plt.plot(dates_optimized, profit_optimized, label='Optimised thresholds', color='blue')
    plt.axhline(y=0, color='black', linestyle='--')
    plt.title('Profit after each trade')
    plt.legend()

    plt.tight_layout()
    plt.savefig(f'{ticker}_stochastic_backtest.png', dpi=120)
    plt.show()


ticker = 'TSLA'
prices = yf.download(ticker, start='2014-01-01', end='2024-01-01', interval='1d', auto_adjust=False)
if isinstance(prices.columns, pd.MultiIndex):        # newer yfinance returns (field, ticker) columns
    prices.columns = prices.columns.get_level_values(0)

prices = calculate_stochastic_oscillator(prices)

best_overbought, best_oversold, best_sharpe = optimize_stochastic_parameters(prices)

signals_default = generate_stochastic_signals(prices)
signals_optimized = generate_stochastic_signals(prices, best_overbought, best_oversold)

final_profit_default, profit_default, trade_dates_default, successful_trades_default, unsuccessful_trades_default, sharpe_ratio_default, stop_loss_trades_default, take_profit_trades_default, cumulative_profit_default = backtest_strategy(signals_default)
final_profit_optimized, profit_optimized, trade_dates_optimized, successful_trades_optimized, unsuccessful_trades_optimized, sharpe_ratio_optimized, stop_loss_trades_optimized, take_profit_trades_optimized, cumulative_profit_optimized = backtest_strategy(signals_optimized)

print(f'Optimized Strategy: Profit = {final_profit_optimized:.2f}, Sharpe Ratio = {sharpe_ratio_optimized:.2f}')
print(f'Default Strategy:   Profit = {final_profit_default:.2f}, Sharpe Ratio = {sharpe_ratio_default:.2f}')
print(f'Optimized Overbought = {best_overbought}, Oversold = {best_oversold}')

plot_graphs()
