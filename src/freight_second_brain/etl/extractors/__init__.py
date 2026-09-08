from freight_second_brain.etl.extractors.comtrade import ComtradeExtractor
from freight_second_brain.etl.extractors.data360_maritime import Data360MaritimeExtractor
from freight_second_brain.etl.extractors.eia_coal import EiaCoalExtractor
from freight_second_brain.etl.extractors.fao_fpi import FaoFpiExtractor
from freight_second_brain.etl.extractors.hellenic_rss import HellenicRssExtractor
from freight_second_brain.etl.extractors.mendeley_bdi import MendeleyBdiExtractor
from freight_second_brain.etl.extractors.noaa_enso import NoaaEnsoExtractor
from freight_second_brain.etl.extractors.qualitative_pages import QualitativePagesExtractor
from freight_second_brain.etl.extractors.trading_economics_bdi import TradingEconomicsBdiExtractor
from freight_second_brain.etl.extractors.usda_psd import UsdaPsdExtractor
from freight_second_brain.etl.extractors.world_bank_api import WorldBankApiExtractor
from freight_second_brain.etl.extractors.world_bank_pink_sheet import WorldBankPinkSheetExtractor
from freight_second_brain.etl.extractors.yahoo_finance import YahooFinanceExtractor

EXTRACTORS = {
    WorldBankPinkSheetExtractor.name: WorldBankPinkSheetExtractor,
    WorldBankApiExtractor.name: WorldBankApiExtractor,
    FaoFpiExtractor.name: FaoFpiExtractor,
    UsdaPsdExtractor.name: UsdaPsdExtractor,
    ComtradeExtractor.name: ComtradeExtractor,
    MendeleyBdiExtractor.name: MendeleyBdiExtractor,
    YahooFinanceExtractor.name: YahooFinanceExtractor,
    NoaaEnsoExtractor.name: NoaaEnsoExtractor,
    Data360MaritimeExtractor.name: Data360MaritimeExtractor,
    EiaCoalExtractor.name: EiaCoalExtractor,
    HellenicRssExtractor.name: HellenicRssExtractor,
    TradingEconomicsBdiExtractor.name: TradingEconomicsBdiExtractor,
    QualitativePagesExtractor.name: QualitativePagesExtractor,
}

__all__ = ["EXTRACTORS"]
