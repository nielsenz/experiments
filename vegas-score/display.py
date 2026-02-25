"""
CLI display module for the Las Vegas Health Score.
Renders scores, bar charts, and composite gauges in the terminal.
"""

from datetime import datetime


class Display:

    GRADE_COLORS = {
        "A": "\033[92m",  # Green
        "B": "\033[96m",  # Cyan
        "C": "\033[93m",  # Yellow
        "D": "\033[91m",  # Red
        "F": "\033[31m",  # Dark Red
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    def header(self):
        print()
        print(f"  {self.BOLD}🎰  LAS VEGAS HEALTH SCORE{self.RESET}")
        print(f"  {self.DIM}📍  Seven Hills, Henderson, NV 89052{self.RESET}")
        print(f"  {self.DIM}📅  {datetime.now().strftime('%A, %B %d, %Y %I:%M %p')}{self.RESET}")
        print(f"  {'─' * 54}")

    def section(self, title):
        print()
        print(f"  {self.BOLD}{'─' * 54}{self.RESET}")
        print(f"  {self.BOLD}  {title}{self.RESET}")
        print(f"  {self.BOLD}{'─' * 54}{self.RESET}")

    def scores(self, score_data):
        """Display scored indicators with bar visualization."""
        overall = score_data.get("overall")
        items = {k: v for k, v in score_data.items() if k != "overall"}

        for key, info in items.items():
            score = info.get("score")
            label = info.get("label", "")
            name = key.replace("_", " ").title()

            if score is None:
                bar = f"{self.DIM}{'░' * 20} N/A{self.RESET}"
                print(f"    {name:<24s} {bar}  {self.DIM}{label}{self.RESET}")
                continue

            filled = round(score / 5)  # 20-char bar
            empty = 20 - filled
            grade = self._grade(score)
            color = self.GRADE_COLORS.get(grade, "")

            bar_str = f"{color}{'█' * filled}{'░' * empty}{self.RESET}"
            score_str = f"{color}{score:5.1f}{self.RESET}"
            grade_str = f"{color}{grade}{self.RESET}"

            print(f"    {name:<24s} {bar_str} {score_str} {grade_str}  {self.DIM}{label}{self.RESET}")

        if overall is not None:
            grade = self._grade(overall)
            color = self.GRADE_COLORS.get(grade, "")
            print(f"    {'─' * 50}")
            print(f"    {'OVERALL':<24s} {' ' * 21}{color}{self.BOLD}{overall:5.1f} {grade}{self.RESET}")

    def composite(self, composite_score, env_score, econ_score):
        """Display the final composite score with gauge."""
        self.section("COMPOSITE LAS VEGAS HEALTH SCORE")
        grade = self._grade(composite_score)
        color = self.GRADE_COLORS.get(grade, "")

        # Big number display
        print()
        print(f"             {color}{self.BOLD}╔═══════════════════╗{self.RESET}")
        print(f"             {color}{self.BOLD}║                   ║{self.RESET}")
        print(f"             {color}{self.BOLD}║    {composite_score:5.1f}  / 100    ║{self.RESET}")
        print(f"             {color}{self.BOLD}║     Grade: {grade}       ║{self.RESET}")
        print(f"             {color}{self.BOLD}║                   ║{self.RESET}")
        print(f"             {color}{self.BOLD}╚═══════════════════╝{self.RESET}")
        print()

        # Sub-scores
        env_grade = self._grade(env_score) if env_score else "?"
        econ_grade = self._grade(econ_score) if econ_score else "?"
        env_color = self.GRADE_COLORS.get(env_grade, "")
        econ_color = self.GRADE_COLORS.get(econ_grade, "")

        env_bar = self._mini_bar(env_score)
        econ_bar = self._mini_bar(econ_score)

        print(f"    🌡️  Environmental  {env_bar}  {env_color}{env_score:5.1f} {env_grade}{self.RESET}")
        print(f"    💰 Economic       {econ_bar}  {econ_color}{econ_score:5.1f} {econ_grade}{self.RESET}")
        print()

    def footer(self, demo=False):
        print(f"\n  {'─' * 54}")
        if demo:
            print(f"  {self.DIM}⚠️  DEMO MODE — using sample data, not live APIs{self.RESET}")
        print(f"  {self.DIM}Scores: 0-100 | A(90+) B(75+) C(60+) D(40+) F(<40){self.RESET}")
        print(f"  {self.DIM}Sources: NWS, AirNow, EPA, USGS, USBR, BLS, Census, EIA, FRED{self.RESET}")
        print()

    def _grade(self, score):
        if score is None:
            return "?"
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"

    def _mini_bar(self, score):
        if score is None:
            return f"{self.DIM}{'░' * 20}{self.RESET}"
        filled = round(score / 5)
        empty = 20 - filled
        grade = self._grade(score)
        color = self.GRADE_COLORS.get(grade, "")
        return f"{color}{'█' * filled}{'░' * empty}{self.RESET}"
