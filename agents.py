from mesa import Agent

# Currency identifiers - used a keys throughout the model
CBDC = 0 # central bank digital currency, fixed exchange rate
OCC1 = 1 # open cryptocurrency 1
OCC2 = 2 # open cryptocurrency 2

class Household(Agent):
    """
    Household agent for the ABM-E-Monies model
    (Markose & Giansante, Phase 1).

    Each household holds three currencies, a stock of the e-good, and a
    price threshold that decides whether it buys or sells this tick.
    A fixed proportion are miners, who convert their receipts into the
    most valuable cryptocurrency.

    Attributes
    ----------
    hid : int
        Explicit household index (0..H-1). Mesa 3 auto-assigns unique_id
        globally across all agents, so we keep our own index for list
        lookups and for the network edge records.
    wealth_map : dict[int, float]
        Holdings by currency id — {0: cash/CBDC, 1: OCC1, 2: OCC2}.
    wealth_increase_map : dict[int, float]
        Receipts ledger: currency received since the last mining step.
        Reset to zero after a miner converts.
    miner : bool
        Whether this household can mine cryptocurrency.
    goods : int
        Stock of the e-good.
    threshold : float
        Individual price threshold. Sells when the forecast price
        exceeds it, buys otherwise.
    buyer, seller : bool
        Mutually exclusive — set together, as in the Java.
    trade_quantity : int
        Goods this household intends to trade this tick.
    wealth : float
        Computed each tick by calculate_wealth().
    """

    def __init__(self, model, hid, cash, occ1, occ2, miner, goods, threshold):
        super().__init__(model)

        self.hid = hid
        self.wealth_map = {CBDC: cash, OCC1: occ1, OCC2: occ2}
        self.wealth_increase_map = {CBDC: 0.0, OCC1: 0.0, OCC2: 0.0}
        self.miner = miner # miner? I hardly know her!
        self.goods = goods
        self.threshold = threshold

        self.buyer = False
        self.seller = False
        self.trade_quantity = 0
        self.wealth = 0.0

    # --- buyer / seller state (mirrors the paired Java setters) ---

    def set_seller(self, value: bool):
        self.seller = value
        self.buyer = not value

    def set_buyer(self, value: bool):
        self.buyer = value
        self.seller = not value

    # --- holdings ---

    def get_wealth(self, currency_id: int) -> float:
        return self.wealth_map[currency_id]

    def set_wealth(self, currency_id: int, coins: float):
        self.wealth_map[currency_id] = coins

    def increase_wealth(self, currency_id: int, coins: float):
        """Credit holdings AND record the receipt in the ledger.
        The ledger is what miners later convert."""
        self.wealth_map[currency_id] += coins
        self.wealth_increase_map[currency_id] += coins

    def decrease_wealth(self, currency_id: int, coins: float):
        """Debit holdings only — deliberately does not touch the ledger,
        matching the Java."""
        self.wealth_map[currency_id] -= coins

    def reset_wealth_increase(self):
        self.wealth_increase_map = {CBDC: 0.0, OCC1: 0.0, OCC2: 0.0}

    def wealth_change(self) -> bool:
        """True if any cryptocurrency was received since the last reset.
        Present in the Java but only referenced by a disabled branch."""
        return any(self.wealth_increase_map[i] > 0 for i in (OCC1, OCC2))

    # --- trade quantity ---

    def set_trade_quantity(self, quantity: int):
        """Never negative — matches the Java guard."""
        self.trade_quantity = quantity if quantity > 0 else 0

    # --- wealth valuation ---

    def calculate_wealth(self, exchange_rates: dict, good_price: float):
        """
        Value the household's portfolio.

        FAITHFUL REPLICATION OF A JAVA BUG. The original reads:

            wealth = 0;
            for(int id : wealthMap.keySet()){
                wealth =+ wealthMap.get(id) * exchangeRates.get(id);
            }
            wealth += goods * goodPrice;

        `=+` is assignment with a unary plus, not `+=`. The loop therefore
        overwrites rather than accumulates, and only the final key survives.
        HashMap<Integer,Double> with keys 0,1,2 iterates in that order, so
        the surviving term is OCC2. Cash and OCC1 contribute nothing to any
        wealth figure reported in the paper.

        Reproduced here so our output matches the published charts. The
        corrected version is a one-line change (use += and drop the comment).
        """
        self.wealth = 0.0
        for currency_id in (CBDC, OCC1, OCC2):
            self.wealth = self.wealth_map[currency_id] * exchange_rates[currency_id]
        self.wealth += self.goods * good_price
