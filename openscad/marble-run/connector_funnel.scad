// connector-funnel (purple) — thin landing connector: conical bowl -> bore + stud.
use <lib.scad>

module mr_connector() {
  difference() {
    connector_solid();
    cut_bowl();
    cut_through_mini();
  }
}

mr_connector();
