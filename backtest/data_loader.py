"""
历史数据加载器
支持从CSV、交易所API等加载K线数据
"""
import pandas as pd
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class KlineData:
    """K线数据"""
    def __init__(
        self,
        timestamp: datetime,
        open: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: Decimal,
        funding_rate: Optional[Decimal] = None
    ):
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.funding_rate = funding_rate


class DataLoader:
    """数据加载器"""
    
    @staticmethod
    def load_from_csv(
        filepath: str,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[KlineData]:
        """
        从CSV加载K线数据
        
        CSV格式要求:
        timestamp,open,high,low,close,volume,funding_rate(可选)
        
        Args:
            filepath: CSV文件路径
            symbol: 交易对
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            K线数据列表
        """
        try:
            df = pd.read_csv(filepath)
            
            # 验证必需列
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                raise ValueError(f"CSV缺少必需列: {required_cols}")
            
            # 转换时间戳
            if df['timestamp'].dtype == 'int64':
                # 假设是毫秒时间戳
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # 时间过滤
            if start_time:
                df = df[df['timestamp'] >= start_time]
            if end_time:
                df = df[df['timestamp'] <= end_time]
            
            # 转换为KlineData对象
            klines = []
            for _, row in df.iterrows():
                kline = KlineData(
                    timestamp=row['timestamp'].to_pydatetime(),
                    open=Decimal(str(row['open'])),
                    high=Decimal(str(row['high'])),
                    low=Decimal(str(row['low'])),
                    close=Decimal(str(row['close'])),
                    volume=Decimal(str(row['volume'])),
                    funding_rate=Decimal(str(row['funding_rate'])) if 'funding_rate' in df.columns else None
                )
                klines.append(kline)
            
            logger.info(f"从CSV加载了 {len(klines)} 条K线数据")
            return klines
            
        except Exception as e:
            logger.error(f"加载CSV失败: {e}")
            raise
    
    @staticmethod
    def generate_sample_data(
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        interval_hours: int = 1
    ) -> List[KlineData]:
        """
        生成示例数据(用于测试)
        
        Args:
            symbol: 交易对
            start_time: 开始时间
            end_time: 结束时间
            interval_hours: K线间隔(小时)
        
        Returns:
            K线数据列表
        """
        import random
        from datetime import timedelta
        
        klines = []
        current_time = start_time
        base_price = Decimal("50000")  # BTC基础价格
        
        while current_time <= end_time:
            # 生成随机价格波动
            volatility = Decimal(str(random.uniform(-0.02, 0.02)))  # ±2%波动
            
            open_price = base_price
            close_price = base_price * (1 + volatility)
            high_price = max(open_price, close_price) * Decimal("1.005")
            low_price = min(open_price, close_price) * Decimal("0.995")
            
            volume = Decimal(str(random.uniform(100, 1000)))
            funding_rate = Decimal(str(random.uniform(-0.001, 0.001)))  # ±0.1%
            
            kline = KlineData(
                timestamp=current_time,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                funding_rate=funding_rate
            )
            klines.append(kline)
            
            # 更新基础价格和时间
            base_price = close_price
            current_time += timedelta(hours=interval_hours)
        
        logger.info(f"生成了 {len(klines)} 条示例K线数据")
        return klines
    
    @staticmethod
    def save_to_csv(klines: List[KlineData], filepath: str):
        """
        保存K线数据到CSV
        
        Args:
            klines: K线数据列表
            filepath: 保存路径
        """
        data = {
            'timestamp': [k.timestamp for k in klines],
            'open': [float(k.open) for k in klines],
            'high': [float(k.high) for k in klines],
            'low': [float(k.low) for k in klines],
            'close': [float(k.close) for k in klines],
            'volume': [float(k.volume) for k in klines],
        }
        
        if klines[0].funding_rate is not None:
            data['funding_rate'] = [float(k.funding_rate) for k in klines]
        
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
        logger.info(f"保存了 {len(klines)} 条K线数据到 {filepath}")
    
    @staticmethod
    def resample_klines(
        klines: List[KlineData],
        target_interval: str = '1h'
    ) -> List[KlineData]:
        """
        重采样K线数据到不同时间周期
        
        Args:
            klines: 原始K线数据
            target_interval: 目标周期 ('1h', '4h', '1d' 等)
        
        Returns:
            重采样后的K线数据
        """
        if not klines:
            return []
        
        # 转换为DataFrame
        df = pd.DataFrame([
            {
                'timestamp': k.timestamp,
                'open': float(k.open),
                'high': float(k.high),
                'low': float(k.low),
                'close': float(k.close),
                'volume': float(k.volume),
                'funding_rate': float(k.funding_rate) if k.funding_rate else None
            }
            for k in klines
        ])
        
        df.set_index('timestamp', inplace=True)
        
        # 重采样
        resampled = df.resample(target_interval).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'funding_rate': 'mean'
        }).dropna()
        
        # 转换回KlineData对象
        result = []
        for timestamp, row in resampled.iterrows():
            kline = KlineData(
                timestamp=timestamp.to_pydatetime(),
                open=Decimal(str(row['open'])),
                high=Decimal(str(row['high'])),
                low=Decimal(str(row['low'])),
                close=Decimal(str(row['close'])),
                volume=Decimal(str(row['volume'])),
                funding_rate=Decimal(str(row['funding_rate'])) if pd.notna(row['funding_rate']) else None
            )
            result.append(kline)
        
        logger.info(f"重采样完成: {len(klines)} -> {len(result)} 条数据")
        return result
