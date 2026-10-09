/* Recorded sample of a real GET /v1/waqt response (values unmodified), used ONLY as the clearly-labelled
   demonstration fallback when the live API is unreachable. It is frozen: demo mode never ticks, so it cannot
   be mistaken for a live clock. Regenerate with tools/record_demo.py. */
window.WAQT_DEMO = {
 "label": "Recorded sample \u2014 NOT live data",
 "source": "GET /v1/waqt?lat=9.0192&lon=38.7525&calendar_provider=umm-al-qura&instant=2026-10-08T09%3A00%3A00Z",
 "api_version": "1.6.0",
 "recorded": "2026-10-08 (local run of this repository's API)",
 "data": {
  "status": "OK",
  "instant": "2026-10-08T09:00:00+00:00",
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
   "maghrib_open": "2026-10-07T15:12:33+00:00",
   "maghrib_close": "2026-10-08T15:12:01+00:00",
   "length_si_seconds": 86368.364,
   "note": "Day is shorter than 24:00:00 today; the reading will reset before conventional midnight would."
  },
  "hijri": {
   "date": "1448-04-27",
   "display": "27 Rabi al-Thani 1448 AH",
   "year": 1448,
   "month": 4,
   "month_name": "Rabi al-Thani",
   "day": 27,
   "provider": {
    "name": "umm-al-qura",
    "version": "astronomical-approx-2002-rules-v1"
   },
   "source_note": null,
   "source": "local",
   "provenance": null
  },
  "calendar_error": null,
  "weekday": "al-Khamis",
  "waqt": {
   "display": "Waqt 17:47:26",
   "reading": {
    "display": "17:47:26",
    "seconds": 64046.544
   }
  },
  "events": [
   {
    "name": "fajr",
    "instant": "2026-10-08T02:03:13+00:00",
    "reading": {
     "display": "10:50:40",
     "seconds": 39040.16
    }
   },
   {
    "name": "sunrise",
    "instant": "2026-10-08T03:12:58+00:00",
    "reading": {
     "display": "12:00:24",
     "seconds": 43224.81
    }
   },
   {
    "name": "dhuhr",
    "instant": "2026-10-08T09:12:33+00:00",
    "reading": {
     "display": "18:00:00",
     "seconds": 64800.202
    }
   },
   {
    "name": "asr",
    "instant": "2026-10-08T12:31:09+00:00",
    "reading": {
     "display": "21:18:36",
     "seconds": 76716.12
    }
   },
   {
    "name": "maghrib",
    "instant": "2026-10-08T15:12:01+00:00",
    "reading": {
     "display": "23:59:28",
     "seconds": 86368.364
    }
   },
   {
    "name": "isha",
    "instant": "2026-10-08T16:17:43+00:00",
    "reading": {
     "display": "25:05:09",
     "seconds": 90309.597
    }
   }
  ],
  "event_representations": [
   {
    "name": "fajr",
    "gregorian": {
     "utc": "2026-10-08T02:03:13+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-08T05:03:13+03:00",
     "local_date": "2026-10-08",
     "local_time": "05:03:13"
    },
    "hijri": {
     "date": "1448-04-27",
     "provider": "umm-al-qura",
     "version": "astronomical-approx-2002-rules-v1",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 10:50:40",
     "seconds": 39040.16
    }
   },
   {
    "name": "sunrise",
    "gregorian": {
     "utc": "2026-10-08T03:12:58+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-08T06:12:58+03:00",
     "local_date": "2026-10-08",
     "local_time": "06:12:58"
    },
    "hijri": {
     "date": "1448-04-27",
     "provider": "umm-al-qura",
     "version": "astronomical-approx-2002-rules-v1",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 12:00:24",
     "seconds": 43224.81
    }
   },
   {
    "name": "dhuhr",
    "gregorian": {
     "utc": "2026-10-08T09:12:33+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-08T12:12:33+03:00",
     "local_date": "2026-10-08",
     "local_time": "12:12:33"
    },
    "hijri": {
     "date": "1448-04-27",
     "provider": "umm-al-qura",
     "version": "astronomical-approx-2002-rules-v1",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 18:00:00",
     "seconds": 64800.202
    }
   },
   {
    "name": "asr",
    "gregorian": {
     "utc": "2026-10-08T12:31:09+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-08T15:31:09+03:00",
     "local_date": "2026-10-08",
     "local_time": "15:31:09"
    },
    "hijri": {
     "date": "1448-04-27",
     "provider": "umm-al-qura",
     "version": "astronomical-approx-2002-rules-v1",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 21:18:36",
     "seconds": 76716.12
    }
   },
   {
    "name": "maghrib",
    "gregorian": {
     "utc": "2026-10-08T15:12:01+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-08T18:12:01+03:00",
     "local_date": "2026-10-08",
     "local_time": "18:12:01"
    },
    "hijri": {
     "date": "1448-04-27",
     "provider": "umm-al-qura",
     "version": "astronomical-approx-2002-rules-v1",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 23:59:28",
     "seconds": 86368.364
    }
   },
   {
    "name": "isha",
    "gregorian": {
     "utc": "2026-10-08T16:17:43+00:00",
     "timezone": "Africa/Addis_Ababa",
     "local": "2026-10-08T19:17:43+03:00",
     "local_date": "2026-10-08",
     "local_time": "19:17:43"
    },
    "hijri": {
     "date": "1448-04-27",
     "provider": "umm-al-qura",
     "version": "astronomical-approx-2002-rules-v1",
     "source": "local",
     "basis": "waqt-day-label"
    },
    "waqt": {
     "display": "Waqt 25:05:09",
     "seconds": 90309.597
    }
   }
  ],
  "next_event": {
   "name": "dhuhr",
   "instant": "2026-10-08T09:12:33+00:00",
   "countdown": {
    "display": "00:12:33",
    "seconds": 753.658
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
 },
 "own_day_isha": {
  "next_event_after_open": {
   "name": "isha",
   "instant": "2026-10-07T16:18:12+00:00",
   "countdown": {
    "display": "01:05:38",
    "seconds": 3938.507
   }
  },
  "reading_at_event": {
   "display": "01:05:38",
   "seconds": 3938.544
  }
 }
};
