#!/usr/bin/env python3
"""Candidate metadata collector; deployment/activation requires separate approval."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.observation_collector import main
if __name__=='__main__':main()
