/* Recorded sample of a real GET /v1/waqt response (values unmodified), used ONLY as the clearly-labelled
   demonstration fallback when the live API is unreachable. It is frozen: demo mode never ticks, so it cannot
   be mistaken for a live clock. Regenerate with the request recorded in `source`. */
window.WAQT_DEMO = {
 "label": "Recorded sample \u2014 NOT live data",
 "source": "GET /v1/waqt?lat=9.0192&lon=38.7525&instant=2026-10-06T19:35:34Z",
 "api_version": "1.6.0",
 "recorded": "2026-10-06 (local run of this repository's API)",
 "data": {
  "status": "OK",
  "instant": "2026-10-06T19:35:34+00:00",
  "location": {
   "lat": 9.0192,
   "lon": 38.7525,
   "elevation_m": 0.0
  },
  "timezone": {
   "name": "Africa/Addis_Ababa",
   "utc_offset_seconds": 10800
  },
  "undefined_reason": null,
  "day": {
   "maghrib_open": "2026-10-06T15:13:05+00:00",
   "maghrib_close": "2026-10-07T15:12:33+00:00",
   "length_si_seconds": 86367.918,
   "note": "Day is shorter than 24:00:00 today; the reading will reset before conventional midnight would."
  },
  "hijri": {
   "date": "1448-04-24",
   "display": "24 Rabi al-Thani 1448 AH",
   "year": 1448,
   "month": 4,
   "month_name": "Rabi al-Thani",
   "day": 24,
   "provider": {
    "name": "arithmetic-tabular",
    "version": "30-year-cycle-epoch-1948440"
   },
   "source_note": null,
   "source": "local",
   "provenance": null
  },
  "calendar_error": null,
  "weekday": "al-Arbiaa",
  "waqt": {
   "display": "Waqt 04:22:28",
   "reading": {
    "display": "04:22:28",
    "seconds": 15748.462
   }
  },
  "events": [
   {
    "name": "fajr",
    "instant": "2026-10-07T02:03:18+00:00",
    "reading": {
     "display": "10:50:12",
     "seconds": 39012.997
    }
   },
   {
    "name": "sunrise",
    "instant": "2026-10-07T03:13:01+00:00",
    "reading": {
     "display": "11:59:55",
     "seconds": 43195.478
    }
   },
   {
    "name": "dhuhr",
    "instant": "2026-10-07T09:12:50+00:00",
    "reading": {
     "display": "17:59:45",
     "seconds": 64785.325
    }
   },
   {
    "name": "asr",
    "instant": "2026-10-07T12:31:14+00:00",
    "reading": {
     "display": "21:18:08",
     "seconds": 76688.676
    }
   },
   {
    "name": "maghrib",
    "instant": "2026-10-07T15:12:33+00:00",
    "reading": {
     "display": "23:59:27",
     "seconds": 86367.918
    }
   },
   {
    "name": "isha",
    "instant": "2026-10-07T16:18:12+00:00",
    "reading": {
     "display": "25:05:06",
     "seconds": 90306.968
    }
   }
  ],
  "event_representations": [
   {
    "name": "fajr",
    "gregorian": {
     "utc": "2026-10-07T02:03:18+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-07T05:03:18+03:00",
     "local_date": "2026-10-07",
     "local_time": "05:03:18"
    },
    "hijri": {
     "date": "1448-04-24",
     "provider": "arithmetic-tabular",
     "version": "30-year-cycle-epoch-1948440",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 10:50:12",
     "seconds": 39012.997
    }
   },
   {
    "name": "sunrise",
    "gregorian": {
     "utc": "2026-10-07T03:13:01+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-07T06:13:01+03:00",
     "local_date": "2026-10-07",
     "local_time": "06:13:01"
    },
    "hijri": {
     "date": "1448-04-24",
     "provider": "arithmetic-tabular",
     "version": "30-year-cycle-epoch-1948440",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 11:59:55",
     "seconds": 43195.478
    }
   },
   {
    "name": "dhuhr",
    "gregorian": {
     "utc": "2026-10-07T09:12:50+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-07T12:12:50+03:00",
     "local_date": "2026-10-07",
     "local_time": "12:12:50"
    },
    "hijri": {
     "date": "1448-04-24",
     "provider": "arithmetic-tabular",
     "version": "30-year-cycle-epoch-1948440",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 17:59:45",
     "seconds": 64785.325
    }
   },
   {
    "name": "asr",
    "gregorian": {
     "utc": "2026-10-07T12:31:14+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-07T15:31:14+03:00",
     "local_date": "2026-10-07",
     "local_time": "15:31:14"
    },
    "hijri": {
     "date": "1448-04-24",
     "provider": "arithmetic-tabular",
     "version": "30-year-cycle-epoch-1948440",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 21:18:08",
     "seconds": 76688.676
    }
   },
   {
    "name": "maghrib",
    "gregorian": {
     "utc": "2026-10-07T15:12:33+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-07T18:12:33+03:00",
     "local_date": "2026-10-07",
     "local_time": "18:12:33"
    },
    "hijri": {
     "date": "1448-04-24",
     "provider": "arithmetic-tabular",
     "version": "30-year-cycle-epoch-1948440",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 23:59:27",
     "seconds": 86367.918
    }
   },
   {
    "name": "isha",
    "gregorian": {
     "utc": "2026-10-07T16:18:12+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-07T19:18:12+03:00",
     "local_date": "2026-10-07",
     "local_time": "19:18:12"
    },
    "hijri": {
     "date": "1448-04-24",
     "provider": "arithmetic-tabular",
     "version": "30-year-cycle-epoch-1948440",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 25:05:06",
     "seconds": 90306.968
    }
   }
  ],
  "next_event": {
   "name": "fajr",
   "instant": "2026-10-07T02:03:18+00:00",
   "countdown": {
    "display": "06:27:44",
    "seconds": 23264.535
   }
  },
  "computation": {
   "engine": "waqt-noaa-low-precision",
   "revision": "2",
   "accuracy_level": "B",
   "astronomy_engine": "waqt-noaa-low-precision",
   "timescale_model": "espenak-meeus-2006",
   "delta_t_seconds": 75.563
  }
 }
};
